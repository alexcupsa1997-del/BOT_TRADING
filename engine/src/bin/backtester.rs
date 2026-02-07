use std::fs::File;
use std::path::Path;
use std::time::Instant;
use parquet::file::reader::{FileReader, SerializedFileReader};
use parquet::record::RowAccessor;

// Mock Strategy State
struct Strategy {
    sma_window: usize,
    history: Vec<f64>,
    position: i64, 
    entry_price: f64,
    cash: f64,
    pnl: f64,
}

impl Strategy {
    fn new() -> Self {
        Self {
            sma_window: 50,
            history: Vec::with_capacity(100),
            position: 0,
            entry_price: 0.0,
            cash: 100_000.0,
            pnl: 0.0,
        }
    }

    fn on_tick(&mut self, price: f64) {
        self.history.push(price);
        if self.history.len() > self.sma_window {
            self.history.remove(0);
        }

        if self.history.len() < self.sma_window {
            return;
        }

        let sum: f64 = self.history.iter().sum();
        let sma = sum / self.sma_window as f64;

        if price > sma && self.position <= 0 {
            if self.position == -1 { self.close_position(price); }
            self.open_position(price, 1);
        } else if price < sma && self.position >= 0 {
            if self.position == 1 { self.close_position(price); }
            self.open_position(price, -1);
        }
        
        // MTM
        if self.position == 1 {
            self.pnl = (price - self.entry_price) + (self.cash - 100_000.0);
        } else if self.position == -1 {
            self.pnl = (self.entry_price - price) + (self.cash - 100_000.0);
        } else {
            self.pnl = self.cash - 100_000.0;
        }
    }

    fn open_position(&mut self, price: f64, side: i64) {
        self.position = side;
        self.entry_price = price;
    }

    fn close_position(&mut self, price: f64) {

        let diff = if self.position == 1 { price - self.entry_price } else { self.entry_price - price };
        self.cash += diff;
        self.position = 0;
    }
}

fn main() -> Result<(), String> { // Changed main to return Result for error propagation
    // Try Docker path first, then local fallback
    let paths = vec![
        "/app/data/synthetic_market.parquet",
        "../analysis/data/synthetic_market.parquet", 
        "data/synthetic_market.parquet"
    ];

    let mut file_path_str = "";
    for p in &paths {
       if std::path::Path::new(p).exists() {
           file_path_str = p;
           break;
       }
    }
    
    if file_path_str.is_empty() {
         // Default to docker path to let error bubble up if nothing found
         file_path_str = "/app/data/synthetic_market.parquet";
    }
    
    println!("Loading data from: {}", file_path_str);
    let file = File::open(file_path_str).map_err(|e| format!("Data file not found at {}: {}", file_path_str, e))?;
    
    let reader = SerializedFileReader::new(file).map_err(|e| format!("Failed to create reader: {}", e))?;
    let mut row_iter = reader.get_row_iter(None).map_err(|e| format!("Failed to create iterator: {}", e))?;

    let mut strategy = Strategy::new();
    let start_time = Instant::now();
    let mut i = 0;

    // Stream rows
    while let Some(record) = row_iter.next() {
        if let Ok(row) = record {
            // Parquet columns: symbol_id, timestamp, bid, ask, volume, flags
            // Standard order by default, but verify by name ideally.
            // For now, assume order: symbol (0), ts (1), bid (2), ask (3), vol (4), flags (5)
            
            // Get Bid Price (Column 2)
            // Note: Parquet-rs API is typed.
            let bid = row.get_double(2).expect("Bid should be double");
            
            strategy.on_tick(bid);
            i += 1;

            if i % 100_000 == 0 {
                println!("Processed {} ticks. PnL: {:.2}", i, strategy.pnl);
            }
        }
    }
    
    let duration = start_time.elapsed();
    println!("==================================================");
    println!("Backtest Complete.");
    println!("Process Time: {:.2?}", duration);
    println!("Ticks Processed: {}", i);
    println!("Throughput: {:.2} ticks/sec", i as f64 / duration.as_secs_f64());
    println!("Final PnL: ${:.2}", strategy.pnl);
    println!("==================================================");
    Ok(())
}
