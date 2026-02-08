//+------------------------------------------------------------------+
//|                                                       Bridge.mq5 |
//|                                  Copyright 2026, Economic Trading|
//|                                             https://www.eco.trade|
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Economic Trading"
#property link      "https://www.eco.trade"
#property version   "3.10"

// Enterprise Bridge v3.1
// Multi-Asset + Multi-Broker Smart Symbol Matching

//+------------------------------------------------------------------+
//| Configuration Inputs                                              |
//+------------------------------------------------------------------+
input string   InpAddress  = "localhost";    // Gateway Address
input int      InpPort     = 5555;           // Gateway Port
input bool     InpSafeMode = true;           // Enable Data Integrity Checks
input int      InpTimerMs  = 100;            // Timer interval (ms)

//+------------------------------------------------------------------+
//| Smart Symbol Matching - Multi-Broker Support                      |
//| Each row: Primary name + alternatives (most brokers covered)      |
//+------------------------------------------------------------------+
// Forex Majors (always same across brokers)
string Forex[7][1] = {
   {"EURUSD"}, {"GBPUSD"}, {"USDJPY"}, {"USDCHF"},
   {"EURGBP"}, {"EURJPY"}, {"GBPJPY"}
};

// Gold & Silver (usually same, but some add suffix)
string Metals[2][6] = {
   {"XAUUSD", "GOLD", "XAUUSDm", "XAUUSD.stp", "XAUUSD.a", "XAUUSD.z"},
   {"XAGUSD", "SILVER", "XAGUSDm", "XAGUSD.stp", "XAGUSD.a", "XAGUSD.z"}
};

// US Indices - many variations
string Indices[3][6] = {
   {"US30", "US30Cash", "DJ30", "DJI30", "WallSt30", "US30.cash"},
   {"US500", "US500Cash", "SPX500", "SP500", "S&P500", "US500.cash"},
   {"US100", "US100Cash", "NAS100", "NDX100", "USTECH", "US100.cash"}
};

// Oil - many variations
string Oil[1][6] = {
   {"XTIUSD", "USOIL", "WTI", "CrudeOil", "USOILCash", "USOIL.cash"}
};

// Crypto - broker dependent
string Crypto[2][6] = {
   {"BTCUSD", "BTCUSDm", "BTCUSD.stp", "Bitcoin", "BTC/USD", "BTCUSD.a"},
   {"ETHUSD", "ETHUSDm", "ETHUSD.stp", "Ethereum", "ETH/USD", "ETHUSD.a"}
};

// Active symbols found on this broker
string ActiveSymbols[];
int    ActiveCount = 0;
int    MaxSymbols = 15;  // Max symbols to track

int    socket = INVALID_HANDLE;
uchar  send_buffer[];
int    currentSymbolIndex = 0;

//+------------------------------------------------------------------+
//| SBE Layout Constants                                             |
//+------------------------------------------------------------------+
// Header (8 bytes) + Body (41 bytes) = 49 bytes total
#define MSG_SIZE 49
#define HEADER_SIZE 8
#define BODY_SIZE 41

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   Print("Initializing Enterprise Bridge v3.1 (Smart Symbol Matching)...");
   
   ArrayResize(ActiveSymbols, MaxSymbols);
   ActiveCount = 0;
   
   // === Forex (always same name) ===
   for(int i = 0; i < 7 && ActiveCount < MaxSymbols; i++)
     {
      if(TryAddSymbol(Forex[i][0]))
         Print("  [", ActiveCount, "] ", Forex[i][0], " - OK (Forex)");
     }
   
   // === Metals (try alternatives) ===
   for(int i = 0; i < 2 && ActiveCount < MaxSymbols; i++)
     {
      string found = FindSymbol(Metals, i, 6);
      if(found != "")
         Print("  [", ActiveCount, "] ", found, " - OK (Metal)");
     }
   
   // === Indices (try alternatives) ===
   for(int i = 0; i < 3 && ActiveCount < MaxSymbols; i++)
     {
      string found = FindSymbol(Indices, i, 6);
      if(found != "")
         Print("  [", ActiveCount, "] ", found, " - OK (Index)");
     }
   
   // === Oil (try alternatives) ===
   for(int i = 0; i < 1 && ActiveCount < MaxSymbols; i++)
     {
      string found = FindSymbol(Oil, i, 6);
      if(found != "")
         Print("  [", ActiveCount, "] ", found, " - OK (Oil)");
     }
   
   // === Crypto (try alternatives) ===
   for(int i = 0; i < 2 && ActiveCount < MaxSymbols; i++)
     {
      string found = FindSymbol(Crypto, i, 6);
      if(found != "")
         Print("  [", ActiveCount, "] ", found, " - OK (Crypto)");
     }
   
   Print("Total active symbols: ", ActiveCount);
   
   if(ActiveCount == 0)
     {
      Print("ERROR: No symbols found!");
      return(INIT_FAILED);
     }
   
   if(!Connect())
      return(INIT_FAILED);
      
   Print("Bridge Connected securely to Gateway.");
   
   // Start timer for multi-asset polling
   if(!EventSetMillisecondTimer(InpTimerMs))
     {
      Print("ERROR: Failed to set timer");
      return(INIT_FAILED);
     }
   
   Print("Timer started: ", InpTimerMs, "ms interval");
   Print("profiler initialized (", 1000/InpTimerMs * ActiveCount, " samples per second)");
   
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Try to add a symbol if it exists                                  |
//+------------------------------------------------------------------+
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

//+------------------------------------------------------------------+
//| Find first available symbol from alternatives array               |
//+------------------------------------------------------------------+
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
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   
   if(socket != INVALID_HANDLE)
     {
      SocketClose(socket);
      Print("Socket Closed.");
     }
  }

//+------------------------------------------------------------------+
//| Timer function - Multi-Asset Polling                             |
//+------------------------------------------------------------------+
void OnTimer()
  {
   // Process next symbol in rotation
   if(ActiveCount == 0) return;
   string symbol = ActiveSymbols[currentSymbolIndex];
   int symbolId = currentSymbolIndex + 1;  // 1-indexed
   
   MqlTick tick;
   if(!SymbolInfoTick(symbol, tick))
     {
      // Move to next symbol
      currentSymbolIndex = (currentSymbolIndex + 1) % ActiveCount;
      return;
     }
   
   // Serialize and send tick
   if(!SendTick(symbolId, tick))
     {
      Print("CRITICAL: Send failed for ", symbol, ". Reconnecting...");
      SocketClose(socket);
      socket = INVALID_HANDLE;
      Connect();
     }
   
   // Move to next symbol
   currentSymbolIndex = (currentSymbolIndex + 1) % ActiveCount;
  }

//+------------------------------------------------------------------+
//| OnTick - Also capture ticks on attached chart                    |
//+------------------------------------------------------------------+
void OnTick()
  {
   // Find current symbol index
   int symbolId = -1;
   for(int i = 0; i < ActiveCount; i++)
     {
      if(ActiveSymbols[i] == _Symbol)
        {
         symbolId = i + 1;
         break;
        }
     }
   
   if(symbolId == -1)
      return;  // Symbol not in our list
   
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return;
   
   SendTick(symbolId, tick);
  }

//+------------------------------------------------------------------+
//| Send Tick Data                                                    |
//+------------------------------------------------------------------+
bool SendTick(int symbolId, MqlTick &tick)
  {
   // 3. Serialize to SBE (Little Endian)
   // Header (8) + Body (41) = 49 bytes
   int body_len = 41;
   int msg_size = HEADER_SIZE + body_len;
   ArrayResize(send_buffer, msg_size);
   int offset = 0;

   // --- SBE Header ---
   // BlockLength (u16)
   WriteU16(send_buffer, offset, (ushort)body_len); 
   // TemplateID (u16) = 3 (MarketData)
   WriteU16(send_buffer, offset, 3);
   // SchemaID (u16) = 1
   WriteU16(send_buffer, offset, 1);
   // Version (u16) = 1
   WriteU16(send_buffer, offset, 1);
   
   // --- SBE Body ---
   // SymbolID (i64)
   WriteI64(send_buffer, offset, symbolId);
   // Timestamp (i64)
   WriteI64(send_buffer, offset, tick.time_msc);
   // Bid (decimal9)
   WriteI64(send_buffer, offset, (long)(tick.bid * 1000000000.0 + 0.5));
   // Ask (decimal9)
   WriteI64(send_buffer, offset, (long)(tick.ask * 1000000000.0 + 0.5));
   // Volume (decimal9)
   WriteI64(send_buffer, offset, (long)(tick.volume * 1000000000.0 + 0.5));
   // Flags (u8)
   send_buffer[offset++] = (uchar)tick.flags;

   // 4. Send Frame (Length Prefix + Data)
   return SendFrame(send_buffer);
  }
   
//+------------------------------------------------------------------+
//| Network Helper Functions                                         |
//+------------------------------------------------------------------+
bool Connect()
  {
   static bool warned = false;
   
   socket = SocketCreate();
   if(socket == INVALID_HANDLE)
     {
      int err = GetLastError();
      if(err == 4014 && !warned)
        {
         Print("═══════════════════════════════════════════════════════════════");
         Print("   Socket creation blocked by MT5 security.");
         Print("   To enable: Tools > Options > Expert Advisors");
         Print("   Check: 'Allow DLL imports' and 'Allow network')");  
         Print("   Then run MT5 as Administrator.");
         Print("   Bridge will retry connection on next timer tick.");
         Print("═══════════════════════════════════════════════════════════════");
         warned = true;
        }
      return(false);
     }
     
   if(!SocketConnect(socket, InpAddress, InpPort, 1000))
     {
      int err = GetLastError();
      if(!warned)
        {
         Print("Connection to ", InpAddress, ":", InpPort, " failed. Error: ", err);
         Print("Make sure Docker is running: docker-compose up -d gateway");
         warned = true;
        }
      SocketClose(socket);
      socket = INVALID_HANDLE;
      return(false);
     }
   
   Print("✓ Connected to Gateway at ", InpAddress, ":", InpPort);
   return(true);
  }

bool SendFrame(uchar &data[])
  {
   if(socket == INVALID_HANDLE) return(false);

   // 1. Send Length Prefix (4 bytes Big Endian)
   uint len = ArraySize(data);
   uchar len_buf[4];
   // Big Endian Conversion manually
   len_buf[0] = (uchar)((len >> 24) & 0xFF);
   len_buf[1] = (uchar)((len >> 16) & 0xFF);
   len_buf[2] = (uchar)((len >> 8)  & 0xFF);
   len_buf[3] = (uchar)(len & 0xFF);
   
   if(SocketSend(socket, len_buf, 4) != 4) return(false);

   // 2. Send payload
   if(SocketSend(socket, data, len) != len) return(false);
   
   return(true);
  }

//+------------------------------------------------------------------+
//| Serialization Helpers (Little Endian)                            |
//+------------------------------------------------------------------+
void WriteU16(uchar &arr[], int &off, ushort val)
  {
   arr[off++] = (uchar)(val & 0xFF);
   arr[off++] = (uchar)((val >> 8) & 0xFF);
  }

void WriteI64(uchar &arr[], int &off, long val)
  {
   for(int i=0; i<8; i++)
     {
      arr[off++] = (uchar)(val & 0xFF);
      val >>= 8;
     }
  }

