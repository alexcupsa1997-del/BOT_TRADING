//+------------------------------------------------------------------+
//|                                             GoliathHybrid.mq5    |
//|                              GOLIATH Trading System v2.0         |
//|         Hybrid Mode: MQL5 Indicators + Python AI Signals         |
//+------------------------------------------------------------------+
#property copyright "GOLIATH Trading System"
#property version   "2.00"
#property description "Hybrid EA: Combines local MQL5 indicators with Python AI signals via Gateway"
#property strict

#include <Trade\Trade.mqh>

// =============================================================================
// INPUT PARAMETERS
// =============================================================================

input group "=== Connection Settings ==="
input string   InpGatewayHost   = "localhost"; // Gateway Host
input int      InpGatewayPort   = 8080;        // Gateway HTTP Port
input int      InpPollInterval  = 5;           // Signal Poll Interval (seconds)

input group "=== Hybrid Mode ==="
input bool     InpUsePythonAI   = true;        // Use Python AI Signals
input bool     InpUseMQL5       = true;        // Use MQL5 Indicators
input int      InpMinConfidence = 70;          // Min AI Confidence to trade (%)
input double   InpAIWeight      = 0.6;         // AI Signal Weight (0-1)
input double   InpMQL5Weight    = 0.4;         // MQL5 Signal Weight (0-1)

input group "=== Risk Management ==="
input double   InpLotSize       = 0.1;         // Lot Size
input int      InpStopLoss      = 50;          // Stop Loss (pips)
input int      InpTakeProfit    = 100;         // Take Profit (pips)
input int      InpMaxTrades     = 3;           // Max Concurrent Trades
input bool     InpUseTrailing   = true;        // Use Trailing Stop
input int      InpTrailingStop  = 30;          // Trailing Stop (pips)

input group "=== MQL5 Indicators ==="
input int      InpRSIPeriod     = 14;          // RSI Period
input int      InpMACDFast      = 12;          // MACD Fast
input int      InpMACDSlow      = 26;          // MACD Slow
input int      InpMACDSignal    = 9;           // MACD Signal
input int      InpBBPeriod      = 20;          // Bollinger Period
input double   InpBBDev         = 2.0;         // Bollinger Deviation
input int      InpADXPeriod     = 14;          // ADX Period

// =============================================================================
// GLOBAL VARIABLES
// =============================================================================

CTrade trade;
int magicNumber = 77777;

// Indicator handles
int hRSI, hMACD, hBB, hADX;

// Buffers
double rsiBuffer[], macdMain[], macdSignal[], bbUpper[], bbMid[], bbLower[];
double adxBuffer[], plusDI[], minusDI[];

// AI Signal cache
datetime lastAIUpdate = 0;
int aiSignalDirection = 0;  // -1 SELL, 0 NEUTRAL, 1 BUY
double aiConfidence = 0;
string aiReason = "";

// =============================================================================
// INITIALIZATION
// =============================================================================

int OnInit()
  {
   // Initialize trade object
   trade.SetExpertMagicNumber(magicNumber);
   trade.SetDeviationInPoints(10);
   trade.SetTypeFilling(ORDER_FILLING_IOC);
   
   // Create indicator handles
   hRSI = iRSI(_Symbol, PERIOD_CURRENT, InpRSIPeriod, PRICE_CLOSE);
   hMACD = iMACD(_Symbol, PERIOD_CURRENT, InpMACDFast, InpMACDSlow, InpMACDSignal, PRICE_CLOSE);
   hBB = iBands(_Symbol, PERIOD_CURRENT, InpBBPeriod, 0, InpBBDev, PRICE_CLOSE);
   hADX = iADX(_Symbol, PERIOD_CURRENT, InpADXPeriod);
   
   if(hRSI == INVALID_HANDLE || hMACD == INVALID_HANDLE || 
      hBB == INVALID_HANDLE || hADX == INVALID_HANDLE)
     {
      Print("ERROR: Failed to create indicator handles");
      return(INIT_FAILED);
     }
   
   // Setup buffers
   ArraySetAsSeries(rsiBuffer, true);
   ArraySetAsSeries(macdMain, true);
   ArraySetAsSeries(macdSignal, true);
   ArraySetAsSeries(bbUpper, true);
   ArraySetAsSeries(bbMid, true);
   ArraySetAsSeries(bbLower, true);
   ArraySetAsSeries(adxBuffer, true);
   ArraySetAsSeries(plusDI, true);
   ArraySetAsSeries(minusDI, true);
   
   // Start timer for AI signal polling
   EventSetTimer(InpPollInterval);
   
   PrintBanner();
   
   return(INIT_SUCCEEDED);
  }

void PrintBanner()
  {
   Print("╔═══════════════════════════════════════════════════════════╗");
   Print("║         GOLIATH HYBRID EA v2.0 - INITIALIZED              ║");
   Print("╠═══════════════════════════════════════════════════════════╣");
   Print("║  Symbol: ", _Symbol, " | TF: ", EnumToString(Period()));
   Print("║  Mode: ", GetModeString());
   Print("║  AI Weight: ", InpAIWeight*100, "% | MQL5 Weight: ", InpMQL5Weight*100, "%");
   Print("║  Gateway: ", InpGatewayHost, ":", InpGatewayPort);
   Print("╚═══════════════════════════════════════════════════════════╝");
  }

string GetModeString()
  {
   if(InpUsePythonAI && InpUseMQL5) return "HYBRID (AI + MQL5)";
   if(InpUsePythonAI) return "AI ONLY";
   if(InpUseMQL5) return "MQL5 ONLY";
   return "DISABLED";
  }

// =============================================================================
// DEINITIALIZATION
// =============================================================================

void OnDeinit(const int reason)
  {
   EventKillTimer();
   IndicatorRelease(hRSI);
   IndicatorRelease(hMACD);
   IndicatorRelease(hBB);
   IndicatorRelease(hADX);
   Print("GoliathHybrid EA removed. Reason: ", reason);
  }

// =============================================================================
// TIMER - POLL PYTHON AI SIGNALS
// =============================================================================

void OnTimer()
  {
   if(!InpUsePythonAI) return;
   
   // Fetch AI signal from Gateway
   FetchAISignal();
  }

void FetchAISignal()
  {
   static bool webRequestWarned = false;  // Only warn once
   static bool webRequestDisabled = false;
   
   if(webRequestDisabled) return;  // Skip if already failed
   
   string url = StringFormat("http://%s:%d/api/signal/%s", 
                             InpGatewayHost, InpGatewayPort, _Symbol);
   
   char data[];
   char result[];
   string headers = "Content-Type: application/json\r\n";
   string resultHeaders;
   
   int timeout = 5000;  // 5 seconds
   
   int res = WebRequest("GET", url, headers, timeout, data, result, resultHeaders);
   
   if(res == 200)
     {
      // Parse JSON response
      string response = CharArrayToString(result);
      ParseAISignal(response);
      lastAIUpdate = TimeCurrent();
     }
   else if(res == -1)
     {
      // WebRequest error - check if allowed in MT5 settings
      int error = GetLastError();
      if(error == 4014 && !webRequestWarned)
        {
         Print("═══════════════════════════════════════════════════════════════");
         Print("   WebRequest not configured. Running in MQL5-ONLY mode.");
         Print("   To enable AI signals: Tools > Options > Expert Advisors");
         Print("   Check 'Allow WebRequest' and add: http://localhost");
         Print("═══════════════════════════════════════════════════════════════");
         webRequestWarned = true;
         webRequestDisabled = true;  // Stop trying
        }
     }
  }

void ParseAISignal(string json)
  {
   // Simple JSON parsing for: {"direction": "BUY/SELL/HOLD", "confidence": 85, "reason": "..."}
   
   // Extract direction
   int dirStart = StringFind(json, "\"direction\":");
   if(dirStart != -1)
     {
      if(StringFind(json, "BUY", dirStart) != -1 && StringFind(json, "BUY", dirStart) < dirStart + 30)
         aiSignalDirection = 1;
      else if(StringFind(json, "SELL", dirStart) != -1 && StringFind(json, "SELL", dirStart) < dirStart + 30)
         aiSignalDirection = -1;
      else
         aiSignalDirection = 0;
     }
   
   // Extract confidence
   int confStart = StringFind(json, "\"confidence\":");
   if(confStart != -1)
     {
      string confStr = StringSubstr(json, confStart + 13, 10);
      aiConfidence = StringToDouble(confStr);
     }
   
   // Extract reason
   int reasonStart = StringFind(json, "\"reason\":");
   if(reasonStart != -1)
     {
      int quoteStart = StringFind(json, "\"", reasonStart + 9);
      int quoteEnd = StringFind(json, "\"", quoteStart + 1);
      if(quoteStart != -1 && quoteEnd != -1)
         aiReason = StringSubstr(json, quoteStart + 1, quoteEnd - quoteStart - 1);
     }
   
   PrintFormat("AI Signal: %s (%.0f%%) - %s", 
               aiSignalDirection > 0 ? "BUY" : (aiSignalDirection < 0 ? "SELL" : "HOLD"),
               aiConfidence, aiReason);
  }

// =============================================================================
// MAIN TICK HANDLER
// =============================================================================

void OnTick()
  {
   // Only trade on new bars
   static datetime lastBar = 0;
   datetime currentBar = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(lastBar == currentBar) return;
   lastBar = currentBar;
   
   // Check max trades
   if(CountOpenTrades() >= InpMaxTrades) return;
   
   // Trailing stop management
   if(InpUseTrailing) ManageTrailingStops();
   
   // Get signals
   double mql5Signal = 0;
   double aiSignal = 0;
   
   if(InpUseMQL5)
     {
      mql5Signal = GetMQL5Signal();
     }
   
   if(InpUsePythonAI)
     {
      aiSignal = GetAISignal();
     }
   
   // Combine signals with weights
   double combinedSignal = (mql5Signal * InpMQL5Weight) + (aiSignal * InpAIWeight);
   
   // Log signals
   if(mql5Signal != 0 || aiSignal != 0)
     {
      PrintFormat("Signals: MQL5=%.2f (w=%.1f) | AI=%.2f (w=%.1f) | Combined=%.2f",
                  mql5Signal, InpMQL5Weight, aiSignal, InpAIWeight, combinedSignal);
     }
   
   // Execute trades
   double threshold = 0.5;  // Combined signal threshold
   
   if(combinedSignal >= threshold)
     {
      OpenBuy(combinedSignal);
     }
   else if(combinedSignal <= -threshold)
     {
      OpenSell(MathAbs(combinedSignal));
     }
  }

// =============================================================================
// MQL5 SIGNAL CALCULATION
// =============================================================================

double GetMQL5Signal()
  {
   if(!UpdateIndicators()) return 0;
   
   double signal = 0;
   int signals = 0;
   int totalIndicators = 0;
   
   // RSI
   double rsi = rsiBuffer[1];
   totalIndicators++;
   if(rsi < 30) { signals++; signal += 1; }
   else if(rsi > 70) { signals++; signal -= 1; }
   
   // MACD
   totalIndicators++;
   if(macdMain[2] < macdSignal[2] && macdMain[1] > macdSignal[1])
     { signals++; signal += 1; }  // Bullish cross
   else if(macdMain[2] > macdSignal[2] && macdMain[1] < macdSignal[1])
     { signals++; signal -= 1; }  // Bearish cross
   
   // Bollinger Bands
   double close = iClose(_Symbol, PERIOD_CURRENT, 1);
   totalIndicators++;
   if(close <= bbLower[1]) { signals++; signal += 0.8; }
   else if(close >= bbUpper[1]) { signals++; signal -= 0.8; }
   
   // ADX trend confirmation
   double adx = adxBuffer[1];
   if(adx > 25)  // Strong trend
     {
      if(plusDI[1] > minusDI[1]) signal += 0.3;  // Bullish trend
      else signal -= 0.3;  // Bearish trend
     }
   
   // Normalize to -1 to 1 range
   if(signals > 0) signal /= signals;
   
   return signal;
  }

// =============================================================================
// AI SIGNAL RETRIEVAL
// =============================================================================

double GetAISignal()
  {
   // Check if AI signal is fresh (within last 2 poll intervals)
   if(TimeCurrent() - lastAIUpdate > InpPollInterval * 2)
     {
      return 0;  // Stale signal
     }
   
   // Check confidence threshold
   if(aiConfidence < InpMinConfidence)
     {
      return 0;  // Not confident enough
     }
   
   // Return normalized signal (-1 to 1)
   return aiSignalDirection * (aiConfidence / 100.0);
  }

// =============================================================================
// TRADE EXECUTION
// =============================================================================

void OpenBuy(double confidence)
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double sl = ask - InpStopLoss * point * 10;
   double tp = ask + InpTakeProfit * point * 10;
   
   string comment = StringFormat("GOLIATH BUY [%.0f%%]", confidence * 100);
   
   if(trade.Buy(InpLotSize, _Symbol, ask, sl, tp, comment))
     {
      PrintFormat("✓ BUY @ %.5f | SL: %.5f | TP: %.5f | Conf: %.0f%%", 
                  ask, sl, tp, confidence * 100);
     }
   else
     {
      PrintFormat("✗ BUY failed: %d", GetLastError());
     }
  }

void OpenSell(double confidence)
  {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double sl = bid + InpStopLoss * point * 10;
   double tp = bid - InpTakeProfit * point * 10;
   
   string comment = StringFormat("GOLIATH SELL [%.0f%%]", confidence * 100);
   
   if(trade.Sell(InpLotSize, _Symbol, bid, sl, tp, comment))
     {
      PrintFormat("✓ SELL @ %.5f | SL: %.5f | TP: %.5f | Conf: %.0f%%", 
                  bid, sl, tp, confidence * 100);
     }
   else
     {
      PrintFormat("✗ SELL failed: %d", GetLastError());
     }
  }

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

bool UpdateIndicators()
  {
   if(CopyBuffer(hRSI, 0, 0, 3, rsiBuffer) < 3) return false;
   if(CopyBuffer(hMACD, 0, 0, 3, macdMain) < 3) return false;
   if(CopyBuffer(hMACD, 1, 0, 3, macdSignal) < 3) return false;
   if(CopyBuffer(hBB, 0, 0, 3, bbMid) < 3) return false;
   if(CopyBuffer(hBB, 1, 0, 3, bbUpper) < 3) return false;
   if(CopyBuffer(hBB, 2, 0, 3, bbLower) < 3) return false;
   if(CopyBuffer(hADX, 0, 0, 3, adxBuffer) < 3) return false;
   if(CopyBuffer(hADX, 1, 0, 3, plusDI) < 3) return false;
   if(CopyBuffer(hADX, 2, 0, 3, minusDI) < 3) return false;
   return true;
  }

int CountOpenTrades()
  {
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionSelectByTicket(PositionGetTicket(i)))
        {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
            PositionGetInteger(POSITION_MAGIC) == magicNumber)
            count++;
        }
     }
   return count;
  }

void ManageTrailingStops()
  {
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double trailDist = InpTrailingStop * point * 10;
   
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != magicNumber) continue;
      
      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentSL = PositionGetDouble(POSITION_SL);
      double currentTP = PositionGetDouble(POSITION_TP);
      
      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
        {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double newSL = bid - trailDist;
         if(newSL > openPrice && newSL > currentSL)
            trade.PositionModify(ticket, newSL, currentTP);
        }
      else
        {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double newSL = ask + trailDist;
         if(newSL < openPrice && (currentSL == 0 || newSL < currentSL))
            trade.PositionModify(ticket, newSL, currentTP);
        }
     }
  }
//+------------------------------------------------------------------+
