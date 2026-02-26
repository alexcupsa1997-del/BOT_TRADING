/**
 * Technical Indicator Calculations
 * ─────────────────────────────────
 * Pure functions for computing EMA, SMA, Bollinger Bands, RSI, MACD, VWAP.
 * All inputs/outputs are number arrays aligned to the candle data.
 */

import type { CandleData } from '../store/demoTradingStore';

// ─── SMA ────────────────────────────────────────────────────────────────────

export function calcSMA(data: CandleData[], period: number): (number | null)[] {
    const result: (number | null)[] = [];
    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            result.push(null);
        } else {
            let sum = 0;
            for (let j = 0; j < period; j++) sum += data[i - j].close;
            result.push(sum / period);
        }
    }
    return result;
}

// ─── EMA ────────────────────────────────────────────────────────────────────

export function calcEMA(data: CandleData[], period: number): (number | null)[] {
    const result: (number | null)[] = [];
    const k = 2 / (period + 1);
    let ema: number | null = null;

    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            result.push(null);
        } else if (ema === null) {
            // First EMA = SMA of first `period` values
            let sum = 0;
            for (let j = 0; j < period; j++) sum += data[i - j].close;
            ema = sum / period;
            result.push(ema);
        } else {
            ema = data[i].close * k + ema * (1 - k);
            result.push(ema);
        }
    }
    return result;
}

// ─── Bollinger Bands ────────────────────────────────────────────────────────

export interface BollingerResult {
    upper: (number | null)[];
    middle: (number | null)[];
    lower: (number | null)[];
}

export function calcBollingerBands(
    data: CandleData[],
    period: number = 20,
    stdDev: number = 2,
): BollingerResult {
    const upper: (number | null)[] = [];
    const middle: (number | null)[] = [];
    const lower: (number | null)[] = [];

    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            upper.push(null);
            middle.push(null);
            lower.push(null);
        } else {
            let sum = 0;
            for (let j = 0; j < period; j++) sum += data[i - j].close;
            const sma = sum / period;

            let sqSum = 0;
            for (let j = 0; j < period; j++) sqSum += (data[i - j].close - sma) ** 2;
            const std = Math.sqrt(sqSum / period);

            middle.push(sma);
            upper.push(sma + stdDev * std);
            lower.push(sma - stdDev * std);
        }
    }

    return { upper, middle, lower };
}

// ─── RSI ────────────────────────────────────────────────────────────────────

export function calcRSI(data: CandleData[], period: number = 14): (number | null)[] {
    const result: (number | null)[] = [];

    if (data.length < period + 1) {
        return data.map(() => null);
    }

    // Calculate initial avg gain/loss
    let avgGain = 0;
    let avgLoss = 0;

    for (let i = 1; i <= period; i++) {
        const change = data[i].close - data[i - 1].close;
        if (change > 0) avgGain += change;
        else avgLoss += Math.abs(change);
        result.push(null);
    }

    result[0] = null; // for index 0
    avgGain /= period;
    avgLoss /= period;

    // First RSI
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    result.push(100 - 100 / (1 + rs));

    // Subsequent EMA-smoothed RSI
    for (let i = period + 1; i < data.length; i++) {
        const change = data[i].close - data[i - 1].close;
        const gain = change > 0 ? change : 0;
        const loss = change < 0 ? Math.abs(change) : 0;

        avgGain = (avgGain * (period - 1) + gain) / period;
        avgLoss = (avgLoss * (period - 1) + loss) / period;

        const rsVal = avgLoss === 0 ? 100 : avgGain / avgLoss;
        result.push(100 - 100 / (1 + rsVal));
    }

    return result;
}

// ─── MACD ───────────────────────────────────────────────────────────────────

export interface MACDResult {
    macd: (number | null)[];
    signal: (number | null)[];
    histogram: (number | null)[];
}

export function calcMACD(
    data: CandleData[],
    fastPeriod: number = 12,
    slowPeriod: number = 26,
    signalPeriod: number = 9,
): MACDResult {
    const fastEMA = calcEMA(data, fastPeriod);
    const slowEMA = calcEMA(data, slowPeriod);

    const macd: (number | null)[] = [];
    for (let i = 0; i < data.length; i++) {
        const f = fastEMA[i];
        const s = slowEMA[i];
        macd.push(f !== null && s !== null ? f - s : null);
    }

    // Signal line = EMA of MACD values
    const signal: (number | null)[] = [];
    const k = 2 / (signalPeriod + 1);
    let sigEma: number | null = null;
    let validCount = 0;
    let firstSum = 0;

    for (let i = 0; i < macd.length; i++) {
        const m = macd[i];
        if (m === null) {
            signal.push(null);
            continue;
        }

        validCount++;
        if (validCount <= signalPeriod) {
            firstSum += m;
            if (validCount === signalPeriod) {
                sigEma = firstSum / signalPeriod;
                signal.push(sigEma);
            } else {
                signal.push(null);
            }
        } else {
            sigEma = m * k + sigEma! * (1 - k);
            signal.push(sigEma);
        }
    }

    // Histogram = MACD - Signal
    const histogram: (number | null)[] = [];
    for (let i = 0; i < data.length; i++) {
        const m = macd[i];
        const s = signal[i];
        histogram.push(m !== null && s !== null ? m - s : null);
    }

    return { macd, signal, histogram };
}

// ─── VWAP ───────────────────────────────────────────────────────────────────

export function calcVWAP(data: CandleData[]): (number | null)[] {
    const result: (number | null)[] = [];
    let cumulativeTPV = 0;
    let cumulativeVolume = 0;

    for (const c of data) {
        const typicalPrice = (c.high + c.low + c.close) / 3;
        cumulativeTPV += typicalPrice * c.volume;
        cumulativeVolume += c.volume;
        result.push(cumulativeVolume > 0 ? cumulativeTPV / cumulativeVolume : null);
    }

    return result;
}

// ─── ATR (Average True Range) ───────────────────────────────────────────────

export function calcATR(data: CandleData[], period: number = 14): (number | null)[] {
    if (data.length < 2) return data.map(() => null);

    const trValues: number[] = [data[0].high - data[0].low];

    for (let i = 1; i < data.length; i++) {
        const tr = Math.max(
            data[i].high - data[i].low,
            Math.abs(data[i].high - data[i - 1].close),
            Math.abs(data[i].low - data[i - 1].close),
        );
        trValues.push(tr);
    }

    const result: (number | null)[] = [];
    for (let i = 0; i < trValues.length; i++) {
        if (i < period - 1) {
            result.push(null);
        } else if (i === period - 1) {
            let sum = 0;
            for (let j = 0; j < period; j++) sum += trValues[i - j];
            result.push(sum / period);
        } else {
            const prev = result[i - 1]!;
            result.push((prev * (period - 1) + trValues[i]) / period);
        }
    }
    return result;
}

// ─── Stochastic Oscillator (%K, %D) ────────────────────────────────────────

export interface StochasticResult {
    k: (number | null)[];
    d: (number | null)[];
}

export function calcStochastic(
    data: CandleData[],
    kPeriod: number = 14,
    dPeriod: number = 3,
): StochasticResult {
    const kValues: (number | null)[] = [];

    for (let i = 0; i < data.length; i++) {
        if (i < kPeriod - 1) {
            kValues.push(null);
        } else {
            let highest = -Infinity;
            let lowest = Infinity;
            for (let j = 0; j < kPeriod; j++) {
                highest = Math.max(highest, data[i - j].high);
                lowest = Math.min(lowest, data[i - j].low);
            }
            const range = highest - lowest;
            kValues.push(range === 0 ? 50 : ((data[i].close - lowest) / range) * 100);
        }
    }

    // %D = SMA of %K
    const dValues: (number | null)[] = [];
    for (let i = 0; i < kValues.length; i++) {
        if (i < kPeriod - 1 + dPeriod - 1 || kValues[i] === null) {
            dValues.push(null);
        } else {
            let sum = 0;
            let count = 0;
            for (let j = 0; j < dPeriod; j++) {
                const v = kValues[i - j];
                if (v !== null) { sum += v; count++; }
            }
            dValues.push(count > 0 ? sum / count : null);
        }
    }

    return { k: kValues, d: dValues };
}

// ─── CCI (Commodity Channel Index) ─────────────────────────────────────────

export function calcCCI(data: CandleData[], period: number = 20): (number | null)[] {
    const result: (number | null)[] = [];

    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            result.push(null);
        } else {
            // Typical prices for the window
            let tpSum = 0;
            const tpValues: number[] = [];
            for (let j = 0; j < period; j++) {
                const c = data[i - j];
                const tp = (c.high + c.low + c.close) / 3;
                tpValues.push(tp);
                tpSum += tp;
            }
            const tpMean = tpSum / period;

            // Mean deviation
            let mdSum = 0;
            for (const tp of tpValues) mdSum += Math.abs(tp - tpMean);
            const meanDev = mdSum / period;

            const currentTP = (data[i].high + data[i].low + data[i].close) / 3;
            result.push(meanDev === 0 ? 0 : (currentTP - tpMean) / (0.015 * meanDev));
        }
    }
    return result;
}

// ─── Williams %R ────────────────────────────────────────────────────────────

export function calcWilliamsR(data: CandleData[], period: number = 14): (number | null)[] {
    const result: (number | null)[] = [];

    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            result.push(null);
        } else {
            let highest = -Infinity;
            let lowest = Infinity;
            for (let j = 0; j < period; j++) {
                highest = Math.max(highest, data[i - j].high);
                lowest = Math.min(lowest, data[i - j].low);
            }
            const range = highest - lowest;
            result.push(range === 0 ? -50 : ((highest - data[i].close) / range) * -100);
        }
    }
    return result;
}

// ─── OBV (On Balance Volume) ────────────────────────────────────────────────

export function calcOBV(data: CandleData[]): (number | null)[] {
    if (data.length === 0) return [];
    const result: (number | null)[] = [0];
    let obv = 0;

    for (let i = 1; i < data.length; i++) {
        if (data[i].close > data[i - 1].close) obv += data[i].volume;
        else if (data[i].close < data[i - 1].close) obv -= data[i].volume;
        result.push(obv);
    }
    return result;
}

// ─── Keltner Channel ────────────────────────────────────────────────────────

export interface KeltnerResult {
    upper: (number | null)[];
    middle: (number | null)[];
    lower: (number | null)[];
}

export function calcKeltnerChannel(
    data: CandleData[],
    emaPeriod: number = 20,
    atrPeriod: number = 10,
    multiplier: number = 1.5,
): KeltnerResult {
    const emaValues = calcEMA(data, emaPeriod);
    const atrValues = calcATR(data, atrPeriod);

    const upper: (number | null)[] = [];
    const middle: (number | null)[] = [];
    const lower: (number | null)[] = [];

    for (let i = 0; i < data.length; i++) {
        const e = emaValues[i];
        const a = atrValues[i];
        if (e !== null && a !== null) {
            middle.push(e);
            upper.push(e + multiplier * a);
            lower.push(e - multiplier * a);
        } else {
            upper.push(null);
            middle.push(null);
            lower.push(null);
        }
    }

    return { upper, middle, lower };
}

// ─── Ichimoku Cloud ─────────────────────────────────────────────────────────

export interface IchimokuResult {
    tenkan: (number | null)[];    // Conversion Line (9)
    kijun: (number | null)[];     // Base Line (26)
    senkouA: (number | null)[];   // Leading Span A
    senkouB: (number | null)[];   // Leading Span B (52)
}

function highLowMid(data: CandleData[], end: number, period: number): number | null {
    if (end - period + 1 < 0) return null;
    let high = -Infinity;
    let low = Infinity;
    for (let j = end - period + 1; j <= end; j++) {
        high = Math.max(high, data[j].high);
        low = Math.min(low, data[j].low);
    }
    return (high + low) / 2;
}

export function calcIchimoku(
    data: CandleData[],
    tenkanPeriod: number = 9,
    kijunPeriod: number = 26,
    senkouBPeriod: number = 52,
): IchimokuResult {
    const tenkan: (number | null)[] = [];
    const kijun: (number | null)[] = [];
    const senkouA: (number | null)[] = [];
    const senkouB: (number | null)[] = [];

    for (let i = 0; i < data.length; i++) {
        const t = highLowMid(data, i, tenkanPeriod);
        const k = highLowMid(data, i, kijunPeriod);
        tenkan.push(t);
        kijun.push(k);
        senkouA.push(t !== null && k !== null ? (t + k) / 2 : null);
        senkouB.push(highLowMid(data, i, senkouBPeriod));
    }

    return { tenkan, kijun, senkouA, senkouB };
}

// ─── Parabolic SAR ──────────────────────────────────────────────────────────

export function calcParabolicSAR(
    data: CandleData[],
    step: number = 0.02,
    max: number = 0.2,
): (number | null)[] {
    if (data.length < 2) return data.map(() => null);

    const result: (number | null)[] = [null];
    let isUpTrend = data[1].close > data[0].close;
    let af = step;
    let ep = isUpTrend ? data[0].high : data[0].low;
    let sar = isUpTrend ? data[0].low : data[0].high;

    for (let i = 1; i < data.length; i++) {
        const prevSar = sar;
        sar = prevSar + af * (ep - prevSar);

        if (isUpTrend) {
            // Clamp SAR below prior two lows
            if (i >= 2) sar = Math.min(sar, data[i - 1].low, data[i - 2].low);
            else sar = Math.min(sar, data[i - 1].low);

            if (data[i].low < sar) {
                // Reversal to downtrend
                isUpTrend = false;
                sar = ep;
                ep = data[i].low;
                af = step;
            } else {
                if (data[i].high > ep) {
                    ep = data[i].high;
                    af = Math.min(af + step, max);
                }
            }
        } else {
            // Clamp SAR above prior two highs
            if (i >= 2) sar = Math.max(sar, data[i - 1].high, data[i - 2].high);
            else sar = Math.max(sar, data[i - 1].high);

            if (data[i].high > sar) {
                // Reversal to uptrend
                isUpTrend = true;
                sar = ep;
                ep = data[i].high;
                af = step;
            } else {
                if (data[i].low < ep) {
                    ep = data[i].low;
                    af = Math.min(af + step, max);
                }
            }
        }

        result.push(sar);
    }

    return result;
}

// ─── ADX (Average Directional Index) ────────────────────────────────────────

export interface ADXResult {
    adx: (number | null)[];
    plusDI: (number | null)[];
    minusDI: (number | null)[];
}

export function calcADX(data: CandleData[], period: number = 14): ADXResult {
    if (data.length < period + 1) {
        return { adx: data.map(() => null), plusDI: data.map(() => null), minusDI: data.map(() => null) };
    }

    const plusDM: number[] = [0];
    const minusDM: number[] = [0];
    const trValues: number[] = [data[0].high - data[0].low];

    for (let i = 1; i < data.length; i++) {
        const upMove = data[i].high - data[i - 1].high;
        const downMove = data[i - 1].low - data[i].low;
        plusDM.push(upMove > downMove && upMove > 0 ? upMove : 0);
        minusDM.push(downMove > upMove && downMove > 0 ? downMove : 0);
        trValues.push(Math.max(
            data[i].high - data[i].low,
            Math.abs(data[i].high - data[i - 1].close),
            Math.abs(data[i].low - data[i - 1].close),
        ));
    }

    // Smoothed TR, +DM, -DM
    const smooth = (arr: number[]): number[] => {
        const result: number[] = [];
        let sum = 0;
        for (let i = 0; i < arr.length; i++) {
            if (i < period) {
                sum += arr[i];
                if (i === period - 1) result.push(sum);
                else result.push(0);
            } else {
                const prev = result[result.length - 1];
                result.push(prev - prev / period + arr[i]);
            }
        }
        return result;
    };

    const smoothTR = smooth(trValues);
    const smoothPlusDM = smooth(plusDM);
    const smoothMinusDM = smooth(minusDM);

    const plusDI: (number | null)[] = [];
    const minusDI: (number | null)[] = [];
    const dx: (number | null)[] = [];

    for (let i = 0; i < data.length; i++) {
        if (i < period - 1 || smoothTR[i] === 0) {
            plusDI.push(null);
            minusDI.push(null);
            dx.push(null);
        } else {
            const pdi = (smoothPlusDM[i] / smoothTR[i]) * 100;
            const mdi = (smoothMinusDM[i] / smoothTR[i]) * 100;
            plusDI.push(pdi);
            minusDI.push(mdi);
            const diSum = pdi + mdi;
            dx.push(diSum === 0 ? 0 : (Math.abs(pdi - mdi) / diSum) * 100);
        }
    }

    // ADX = smoothed DX
    const adx: (number | null)[] = [];
    let adxSum = 0;
    let adxCount = 0;
    let adxEma: number | null = null;

    for (let i = 0; i < dx.length; i++) {
        if (dx[i] === null) {
            adx.push(null);
            continue;
        }
        adxCount++;
        if (adxCount <= period) {
            adxSum += dx[i]!;
            if (adxCount === period) {
                adxEma = adxSum / period;
                adx.push(adxEma);
            } else {
                adx.push(null);
            }
        } else {
            adxEma = (adxEma! * (period - 1) + dx[i]!) / period;
            adx.push(adxEma);
        }
    }

    return { adx, plusDI, minusDI };
}
