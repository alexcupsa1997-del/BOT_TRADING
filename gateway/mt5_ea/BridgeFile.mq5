//+------------------------------------------------------------------+
//|                                                   BridgeFile.mq5 |
//|                        GOLIATH Trading System v3.2               |
//|            File-Based Communication (No Socket Required)          |
//+------------------------------------------------------------------+
#property copyright "GOLIATH Trading System"
#property version   "3.20"
#property description "Data Bridge via Files - No network permissions needed"
#property strict

// =============================================================================
// INPUT PARAMETERS
// =============================================================================

input group "=== File Settings ==="
input string   InpDataPath     = "MQL5\\Files\\goliath\\";  // Data folder path
input int      InpTimerMs      = 100;                       // Timer interval (ms)

// =============================================================================
// SYMBOL ARRAYS
// =============================================================================

string Forex[7] = {"EURUSD", "GBPUSD", "USDJPY", "USDCHF", "EURGBP", "EURJPY", "GBPJPY"};
string Metals[2][6] = {
   {"XAUUSD", "GOLD", "XAUUSDm", "XAUUSD.stp", "XAUUSD.a", "XAUUSD.z"},
   {"XAGUSD", "SILVER", "XAGUSDm", "XAGUSD.stp", "XAGUSD.a", "XAGUSD.z"}
};
string Indices[3][6] = {
   {"US30", "DJ30", "US30.cash", "US30m", "DJI", "US30.a"},
   {"US500", "SP500", "SPX500", "US500.cash", "US500m", "SPX"},
   {"NAS100", "USTEC", "NQ100", "NAS100.cash", "NAS100m", "NASDAQ"}
};
string Oil[1][6] = {
   {"USOIL", "WTI", "CL", "XTIUSD", "USOILm", "CRUDEOIL"}
};
string Crypto[2][6] = {
   {"BTCUSD", "BTCUSDm", "BTCUSD.stp", "Bitcoin", "BTC/USD", "BTCUSD.a"},
   {"ETHUSD", "ETHUSDm", "ETHUSD.stp", "Ethereum", "ETH/USD", "ETHUSD.a"}
};

// Active symbols
string ActiveSymbols[];
int ActiveCount = 0;
int MaxSymbols = 15;
int currentSymbolIndex = 0;

// File handles
string tickFile = "";
string signalFile = "";

// =============================================================================
// INITIALIZATION
// =============================================================================

int OnInit()
  {
   Print("╔═══════════════════════════════════════════════════════════════╗");
   Print("║    GOLIATH BRIDGE v3.2 - FILE-BASED COMMUNICATION             ║");
   Print("╠═══════════════════════════════════════════════════════════════╣");
   
   ArrayResize(ActiveSymbols, MaxSymbols);
   
   // Setup file paths
   tickFile = InpDataPath + "ticks.csv";
   signalFile = InpDataPath + "signals.txt";
   
   // Create directory if needed
   FolderCreate(InpDataPath);
   
   // Initialize tick file with header
   int handle = FileOpen(tickFile, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
   if(handle != INVALID_HANDLE)
     {
      FileWrite(handle, "timestamp", "symbol", "bid", "ask", "volume");
      FileClose(handle);
      Print("║  Tick file: ", tickFile);
     }
   else
     {
      Print("║  ERROR: Cannot create tick file");
      return(INIT_FAILED);
     }
   
   // Discover symbols
   Print("║  Discovering symbols...");
   
   // Forex
   for(int i = 0; i < ArraySize(Forex) && ActiveCount < MaxSymbols; i++)
      TryAddSymbol(Forex[i]);
   
   // Metals
   for(int i = 0; i < 2 && ActiveCount < MaxSymbols; i++)
      FindSymbol(Metals, i, 6);
   
   // Indices
   for(int i = 0; i < 3 && ActiveCount < MaxSymbols; i++)
      FindSymbol(Indices, i, 6);
   
   // Oil
   for(int i = 0; i < 1 && ActiveCount < MaxSymbols; i++)
      FindSymbol(Oil, i, 6);
   
   // Crypto
   for(int i = 0; i < 2 && ActiveCount < MaxSymbols; i++)
      FindSymbol(Crypto, i, 6);
   
   Print("║  Active symbols: ", ActiveCount);
   
   for(int i = 0; i < ActiveCount; i++)
      Print("║    [", i+1, "] ", ActiveSymbols[i]);
   
   if(ActiveCount == 0)
     {
      Print("║  ERROR: No symbols found!");
      return(INIT_FAILED);
     }
   
   // Start timer
   if(!EventSetMillisecondTimer(InpTimerMs))
     {
      Print("║  ERROR: Failed to set timer");
      return(INIT_FAILED);
     }
   
   Print("╠═══════════════════════════════════════════════════════════════╣");
   Print("║  ✓ Bridge ready - Writing ticks to files");
   Print("║  ✓ No network permissions required!");
   Print("╚═══════════════════════════════════════════════════════════════╝");
   
   return(INIT_SUCCEEDED);
  }

// =============================================================================
// TIMER - Write Ticks to File
// =============================================================================

void OnTimer()
  {
   if(ActiveCount == 0) return;
   
   string symbol = ActiveSymbols[currentSymbolIndex];
   
   MqlTick tick;
   if(!SymbolInfoTick(symbol, tick))
     {
      currentSymbolIndex = (currentSymbolIndex + 1) % ActiveCount;
      return;
     }
   
   WriteTick(symbol, tick);
   
   currentSymbolIndex = (currentSymbolIndex + 1) % ActiveCount;
  }

// =============================================================================
// WRITE TICK TO FILE
// =============================================================================

void WriteTick(string symbol, MqlTick &tick)
  {
   int handle = FileOpen(tickFile, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
   if(handle == INVALID_HANDLE) return;
   
   // Move to end of file
   FileSeek(handle, 0, SEEK_END);
   
   // Write tick data
   FileWrite(handle, 
      TimeToString(tick.time, TIME_DATE|TIME_SECONDS),
      symbol,
      DoubleToString(tick.bid, 5),
      DoubleToString(tick.ask, 5),
      (string)tick.volume
   );
   
   FileClose(handle);
  }

// =============================================================================
// READ SIGNALS FROM FILE (Optional)
// =============================================================================

void CheckSignals()
  {
   if(!FileIsExist(signalFile)) return;
   
   int handle = FileOpen(signalFile, FILE_READ|FILE_TXT|FILE_ANSI);
   if(handle == INVALID_HANDLE) return;
   
   while(!FileIsEnding(handle))
     {
      string line = FileReadString(handle);
      if(StringLen(line) > 0)
        {
         Print("Signal received: ", line);
         // Process signal here
        }
     }
   
   FileClose(handle);
   
   // Clear the signal file after reading
   FileDelete(signalFile);
  }

// =============================================================================
// ONTICK
// =============================================================================

void OnTick()
  {
   // Check for incoming signals
   CheckSignals();
   
   // Also write tick for attached symbol
   MqlTick tick;
   if(SymbolInfoTick(_Symbol, tick))
      WriteTick(_Symbol, tick);
  }

// =============================================================================
// DEINITIALIZATION
// =============================================================================

void OnDeinit(const int reason)
  {
   EventKillTimer();
   Print("BridgeFile stopped. Reason: ", reason);
  }

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

bool TryAddSymbol(string symbol)
  {
   if(SymbolSelect(symbol, true))
     {
      ActiveSymbols[ActiveCount] = symbol;
      ActiveCount++;
      return true;
     }
   return false;
  }

string FindSymbol(string &arr[][6], int row, int cols)
  {
   for(int j = 0; j < cols; j++)
     {
      if(arr[row][j] == "") continue;
      if(TryAddSymbol(arr[row][j]))
         return arr[row][j];
     }
   return "";
  }
//+------------------------------------------------------------------+
