//+------------------------------------------------------------------+
//|                                              SignalTrader.mq5    |
//|                              GOLIATH Trading System v1.0         |
//|                         Multi-Indicator Signal-Based Trading     |
//+------------------------------------------------------------------+
#property copyright "GOLIATH Trading System"
#property version   "1.00"
#property description "Signal-based trading EA using RSI, MACD, Bollinger Bands"
#property strict

// =============================================================================
// INPUT PARAMETERS
// =============================================================================

input group "=== Strategy Settings ==="
input double   InpLotSize       = 0.1;       // Lot Size
input int      InpStopLoss      = 50;        // Stop Loss (pips)
input int      InpTakeProfit    = 100;       // Take Profit (pips)
input int      InpMaxTrades     = 3;         // Max Concurrent Trades
input bool     InpUseTrailing   = true;      // Use Trailing Stop
input int      InpTrailingStop  = 30;        // Trailing Stop (pips)

input group "=== RSI Settings ==="
input int      InpRSIPeriod     = 14;        // RSI Period
input int      InpRSIOversold   = 30;        // RSI Oversold Level
input int      InpRSIOverbought = 70;        // RSI Overbought Level
input bool     InpUseRSI        = true;      // Use RSI Filter

input group "=== MACD Settings ==="
input int      InpMACDFast      = 12;        // MACD Fast Period
input int      InpMACDSlow      = 26;        // MACD Slow Period
input int      InpMACDSignal    = 9;         // MACD Signal Period
input bool     InpUseMACD       = true;      // Use MACD Filter

input group "=== Bollinger Bands Settings ==="
input int      InpBBPeriod      = 20;        // BB Period
input double   InpBBDeviation   = 2.0;       // BB Deviation
input bool     InpUseBB         = true;      // Use Bollinger Bands

input group "=== ADX Settings ==="
input int      InpADXPeriod     = 14;        // ADX Period
input int      InpADXMinStrength = 20;       // Minimum ADX for trend
input bool     InpUseADX        = true;      // Use ADX Filter

input group "=== Time Filter ==="
input int      InpStartHour     = 8;         // Trading Start Hour (Server)
input int      InpEndHour       = 20;        // Trading End Hour (Server)
input bool     InpUseTimeFilter = false;     // Use Time Filter

// =============================================================================
// GLOBAL VARIABLES
// =============================================================================

int handleRSI;
int handleMACD;
int handleBB;
int handleADX;

double rsiBuffer[];
double macdMainBuffer[];
double macdSignalBuffer[];
double bbUpperBuffer[];
double bbMiddleBuffer[];
double bbLowerBuffer[];
double adxBuffer[];
double plusDIBuffer[];
double minusDIBuffer[];

int magicNumber = 12345;
datetime lastTradeTime = 0;

// =============================================================================
// INITIALIZATION
// =============================================================================

int OnInit()
  {
   // Create indicator handles
   handleRSI = iRSI(_Symbol, PERIOD_CURRENT, InpRSIPeriod, PRICE_CLOSE);
   handleMACD = iMACD(_Symbol, PERIOD_CURRENT, InpMACDFast, InpMACDSlow, InpMACDSignal, PRICE_CLOSE);
   handleBB = iBands(_Symbol, PERIOD_CURRENT, InpBBPeriod, 0, InpBBDeviation, PRICE_CLOSE);
   handleADX = iADX(_Symbol, PERIOD_CURRENT, InpADXPeriod);
   
   // Validate handles
   if(handleRSI == INVALID_HANDLE || handleMACD == INVALID_HANDLE || 
      handleBB == INVALID_HANDLE || handleADX == INVALID_HANDLE)
     {
      Print("ERROR: Failed to create indicator handles");
      return(INIT_FAILED);
     }
   
   // Setup buffers
   ArraySetAsSeries(rsiBuffer, true);
   ArraySetAsSeries(macdMainBuffer, true);
   ArraySetAsSeries(macdSignalBuffer, true);
   ArraySetAsSeries(bbUpperBuffer, true);
   ArraySetAsSeries(bbMiddleBuffer, true);
   ArraySetAsSeries(bbLowerBuffer, true);
   ArraySetAsSeries(adxBuffer, true);
   ArraySetAsSeries(plusDIBuffer, true);
   ArraySetAsSeries(minusDIBuffer, true);
   
   Print("═══════════════════════════════════════════════");
   Print("  GOLIATH SignalTrader EA v1.0 Initialized");
   Print("  Symbol: ", _Symbol, " | TF: ", EnumToString(Period()));
   Print("  Lot: ", InpLotSize, " | SL: ", InpStopLoss, " | TP: ", InpTakeProfit);
   Print("═══════════════════════════════════════════════");
   
   return(INIT_SUCCEEDED);
  }

// =============================================================================
// DEINITIALIZATION
// =============================================================================

void OnDeinit(const int reason)
  {
   IndicatorRelease(handleRSI);
   IndicatorRelease(handleMACD);
   IndicatorRelease(handleBB);
   IndicatorRelease(handleADX);
   
   Print("SignalTrader EA removed. Reason: ", reason);
  }

// =============================================================================
// MAIN TICK HANDLER
// =============================================================================

void OnTick()
  {
   // Check if new bar
   static datetime lastBar = 0;
   datetime currentBar = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(lastBar == currentBar) return;
   lastBar = currentBar;
   
   // Time filter
   if(InpUseTimeFilter && !IsWithinTradingHours())
      return;
   
   // Update trailing stops
   if(InpUseTrailing)
      ManageTrailingStops();
   
   // Check if we can open new trades
   if(CountOpenTrades() >= InpMaxTrades)
      return;
   
   // Get indicator data
   if(!UpdateIndicators())
      return;
   
   // Analyze signals
   int signal = AnalyzeSignals();
   
   // Execute trades
   if(signal == 1)
      OpenBuy();
   else if(signal == -1)
      OpenSell();
  }

// =============================================================================
// SIGNAL ANALYSIS
// =============================================================================

int AnalyzeSignals()
  {
   int buySignals = 0;
   int sellSignals = 0;
   int requiredSignals = 0;
   
   // RSI Analysis
   if(InpUseRSI)
     {
      requiredSignals++;
      double rsi = rsiBuffer[1];  // Previous bar
      
      if(rsi < InpRSIOversold)
        {
         buySignals++;
         PrintFormat("RSI Signal: BUY (RSI=%.1f < %d)", rsi, InpRSIOversold);
        }
      else if(rsi > InpRSIOverbought)
        {
         sellSignals++;
         PrintFormat("RSI Signal: SELL (RSI=%.1f > %d)", rsi, InpRSIOverbought);
        }
     }
   
   // MACD Analysis
   if(InpUseMACD)
     {
      requiredSignals++;
      double macdMain = macdMainBuffer[1];
      double macdSignal = macdSignalBuffer[1];
      double macdMainPrev = macdMainBuffer[2];
      double macdSignalPrev = macdSignalBuffer[2];
      
      // Bullish crossover
      if(macdMainPrev < macdSignalPrev && macdMain > macdSignal)
        {
         buySignals++;
         Print("MACD Signal: BUY (Bullish Crossover)");
        }
      // Bearish crossover
      else if(macdMainPrev > macdSignalPrev && macdMain < macdSignal)
        {
         sellSignals++;
         Print("MACD Signal: SELL (Bearish Crossover)");
        }
     }
   
   // Bollinger Bands Analysis
   if(InpUseBB)
     {
      requiredSignals++;
      double close = iClose(_Symbol, PERIOD_CURRENT, 1);
      double lower = bbLowerBuffer[1];
      double upper = bbUpperBuffer[1];
      
      // Price touches lower band (potential reversal up)
      if(close <= lower)
        {
         buySignals++;
         PrintFormat("BB Signal: BUY (Price %.5f <= Lower %.5f)", close, lower);
        }
      // Price touches upper band (potential reversal down)
      else if(close >= upper)
        {
         sellSignals++;
         PrintFormat("BB Signal: SELL (Price %.5f >= Upper %.5f)", close, upper);
        }
     }
   
   // ADX Trend Filter
   if(InpUseADX)
     {
      double adx = adxBuffer[1];
      double plusDI = plusDIBuffer[1];
      double minusDI = minusDIBuffer[1];
      
      // Only trade if trend is strong enough
      if(adx < InpADXMinStrength)
        {
         PrintFormat("ADX Filter: NO TRADE (ADX=%.1f < %d)", adx, InpADXMinStrength);
         return 0;
        }
      
      // Direction confirmation
      if(plusDI > minusDI)
        {
         if(sellSignals > 0) sellSignals--;  // Reduce contrary signals
        }
      else
        {
         if(buySignals > 0) buySignals--;
        }
     }
   
   // Decision
   int threshold = (requiredSignals > 1) ? 2 : 1;  // Need at least 2 signals if multiple indicators
   
   if(buySignals >= threshold && sellSignals == 0)
     {
      PrintFormat(">>> CONSENSUS: BUY (%d signals)", buySignals);
      return 1;
     }
   else if(sellSignals >= threshold && buySignals == 0)
     {
      PrintFormat(">>> CONSENSUS: SELL (%d signals)", sellSignals);
      return -1;
     }
   
   return 0;
  }

// =============================================================================
// TRADE EXECUTION
// =============================================================================

void OpenBuy()
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double sl = ask - InpStopLoss * point * 10;  // Convert pips to points
   double tp = ask + InpTakeProfit * point * 10;
   
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_DEAL;
   request.symbol = _Symbol;
   request.volume = InpLotSize;
   request.type = ORDER_TYPE_BUY;
   request.price = ask;
   request.sl = sl;
   request.tp = tp;
   request.deviation = 10;
   request.magic = magicNumber;
   request.comment = "GOLIATH BUY";
   request.type_filling = ORDER_FILLING_IOC;
   
   if(OrderSend(request, result))
     {
      if(result.retcode == TRADE_RETCODE_DONE)
        {
         PrintFormat("✓ BUY Order #%d opened at %.5f | SL: %.5f | TP: %.5f", 
                     result.deal, ask, sl, tp);
         lastTradeTime = TimeCurrent();
        }
     }
   else
     {
      PrintFormat("✗ BUY Order failed. Error: %d", GetLastError());
     }
  }

void OpenSell()
  {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double sl = bid + InpStopLoss * point * 10;
   double tp = bid - InpTakeProfit * point * 10;
   
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_DEAL;
   request.symbol = _Symbol;
   request.volume = InpLotSize;
   request.type = ORDER_TYPE_SELL;
   request.price = bid;
   request.sl = sl;
   request.tp = tp;
   request.deviation = 10;
   request.magic = magicNumber;
   request.comment = "GOLIATH SELL";
   request.type_filling = ORDER_FILLING_IOC;
   
   if(OrderSend(request, result))
     {
      if(result.retcode == TRADE_RETCODE_DONE)
        {
         PrintFormat("✓ SELL Order #%d opened at %.5f | SL: %.5f | TP: %.5f", 
                     result.deal, bid, sl, tp);
         lastTradeTime = TimeCurrent();
        }
     }
   else
     {
      PrintFormat("✗ SELL Order failed. Error: %d", GetLastError());
     }
  }

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

bool UpdateIndicators()
  {
   if(CopyBuffer(handleRSI, 0, 0, 3, rsiBuffer) < 3) return false;
   if(CopyBuffer(handleMACD, 0, 0, 3, macdMainBuffer) < 3) return false;
   if(CopyBuffer(handleMACD, 1, 0, 3, macdSignalBuffer) < 3) return false;
   if(CopyBuffer(handleBB, 0, 0, 3, bbMiddleBuffer) < 3) return false;
   if(CopyBuffer(handleBB, 1, 0, 3, bbUpperBuffer) < 3) return false;
   if(CopyBuffer(handleBB, 2, 0, 3, bbLowerBuffer) < 3) return false;
   if(CopyBuffer(handleADX, 0, 0, 3, adxBuffer) < 3) return false;
   if(CopyBuffer(handleADX, 1, 0, 3, plusDIBuffer) < 3) return false;
   if(CopyBuffer(handleADX, 2, 0, 3, minusDIBuffer) < 3) return false;
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

bool IsWithinTradingHours()
  {
   MqlDateTime dt;
   TimeCurrent(dt);
   return (dt.hour >= InpStartHour && dt.hour < InpEndHour);
  }

void ManageTrailingStops()
  {
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double trailPoints = InpTrailingStop * point * 10;
   
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != magicNumber) continue;
      
      double posPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double posSL = PositionGetDouble(POSITION_SL);
      double currentPrice;
      double newSL;
      
      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
        {
         currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         newSL = currentPrice - trailPoints;
         
         if(newSL > posPrice && newSL > posSL)
           {
            MqlTradeRequest req = {};
            MqlTradeResult res = {};
            req.action = TRADE_ACTION_SLTP;
            req.position = ticket;
            req.symbol = _Symbol;
            req.sl = newSL;
            req.tp = PositionGetDouble(POSITION_TP);
            OrderSend(req, res);
           }
        }
      else if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL)
        {
         currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         newSL = currentPrice + trailPoints;
         
         if(newSL < posPrice && (posSL == 0 || newSL < posSL))
           {
            MqlTradeRequest req = {};
            MqlTradeResult res = {};
            req.action = TRADE_ACTION_SLTP;
            req.position = ticket;
            req.symbol = _Symbol;
            req.sl = newSL;
            req.tp = PositionGetDouble(POSITION_TP);
            OrderSend(req, res);
           }
        }
     }
  }
//+------------------------------------------------------------------+
