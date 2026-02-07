use std::fs::File;
use std::io::{self, Read, BufReader};
use std::path::Path;
use engine::domain::value_objects::{Price, Quantity};
use engine::domain::order_typestate::{Side};
use rust_decimal::Decimal;

// SBE Header layout (Little Endian)
// BlockLength (u16), TemplateId (u16), SchemaId (u16), Version (u16)
const HEADER_SIZE: usize = 8;
const BLOCK_LENGTH: usize = 33; // 8+8+1+8+8

#[derive(Debug)]
struct SbeHeader {
    block_length: u16,
    template_id: u16,
    schema_id: u16,
    version: u16,
}

#[derive(Debug)]
struct OrderResult {
    order_id: i64,
    symbol: i64,
    side: char,
    price: Price,
    quantity: Quantity,
}

fn read_u16_le(buf: &[u8]) -> u16 {
    u16::from_le_bytes([buf[0], buf[1]])
}

fn read_i64_le(buf: &[u8]) -> i64 {
    i64::from_le_bytes([buf[0], buf[1], buf[2], buf[3], buf[4], buf[5], buf[6], buf[7]])
}

fn decode_decimal9(buf: &[u8]) -> rust_decimal::Decimal {
    let mantissa = read_i64_le(buf);
    // Decimal::new(mantissa, 9) creates mantissa * 10^-9
    Decimal::new(mantissa, 9)
}

fn process_stream(path: &str) -> io::Result<()> {
    let f = File::open(path)?;
    let mut reader = BufReader::new(f);
    let mut header_buf = [0u8; HEADER_SIZE];
    
    let mut count = 0;

    loop {
        // Read Header
        match reader.read_exact(&mut header_buf) {
            Ok(_) => {},
            Err(e) if e.kind() == io::ErrorKind::UnexpectedEof => break, // EOF
            Err(e) => return Err(e),
        }

        let header = SbeHeader {
            block_length: read_u16_le(&header_buf[0..2]),
            template_id: read_u16_le(&header_buf[2..4]),
            schema_id: read_u16_le(&header_buf[4..6]),
            version: read_u16_le(&header_buf[6..8]),
        };

        if header.template_id != 2 {
            println!("Skipping unknown message ID: {}", header.template_id);
            // Skip body
            let mut skip = vec![0u8; header.block_length as usize];
            reader.read_exact(&mut skip)?;
            continue;
        }

        // Read Body
        let mut body_buf = vec![0u8; header.block_length as usize];
        reader.read_exact(&mut body_buf)?;

        // Decode Layout
        // 0-7: OrderId (i64)
        // 8-15: Symbol (i64)
        // 16: Side (char)
        // 17-24: Price (decimal9)
        // 25-32: Qty (decimal9)

        let order_id = read_i64_le(&body_buf[0..8]);
        let symbol = read_i64_le(&body_buf[8..16]);
        let side = body_buf[16] as char;
        let price_dec = decode_decimal9(&body_buf[17..25]);
        let qty_dec = decode_decimal9(&body_buf[25..33]);

        // Convert to Domain Types (Price/Quantity expect raw i128 scaled to 10^8 usually, but here we construct from Decimal for validation if possible)
        // Actually, our Price/Quantity wrappers wrap i128 scaled. We need a way to convert Decimal to them.
        // Assuming we are just verifying decoding for now.

        println!("MSG #{}: ID={} Sym={} Side={} Px={} Qty={}", 
            count, order_id, symbol, side, price_dec, qty_dec);
        
        count += 1;
    }
    
    println!("Successfully decoded {} messages.", count);
    Ok(())
}

fn main() {
    let path = "../analysis/orders.sbe";
    println!("Reading SBE stream from: {}", path);
    if let Err(e) = process_stream(path) {
        eprintln!("Error processing stream: {}", e);
    }
}
