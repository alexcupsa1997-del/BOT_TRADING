use sha2::{Sha256, Digest};
use std::fs::OpenOptions;
use std::io::Write;
use std::path::Path;
use chrono::Utc;
use serde::{Serialize, Deserialize};

/// Audit Event Structure
/// Represents a critical system action that must be permanently recorded.
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct AuditEvent {
    pub timestamp: i64,
    pub principal: String, // Who did it?
    pub action: String,    // What did they do?
    pub resource: String,  // On what?
    pub details: String,   // Extra context
    pub prev_hash: String, // Link to previous event (Blockchain-style)
}

/// Audit Logger
/// Manages the append-only, cryptographically chained log file.
pub struct AuditLogger {
    file_path: String,
    last_hash: String,
}

impl AuditLogger {
    /// Initialize the logger. 
    /// If file exists, reads the last line to establish the chain.
    pub fn new(path: &str) -> Self {
        let last_hash = Self::recover_last_hash(path).unwrap_or_else(|_| "0000000000000000000000000000000000000000000000000000000000000000".to_string());
        
        Self {
            file_path: path.to_string(),
            last_hash,
        }
    }

    /// Log a critical event.
    /// Returns the hash of the new event.
    pub fn log(&mut self, principal: &str, action: &str, resource: &str, details: &str) -> std::io::Result<String> {
        let event = AuditEvent {
            timestamp: Utc::now().timestamp_millis(),
            principal: principal.to_string(),
            action: action.to_string(),
            resource: resource.to_string(),
            details: details.to_string(),
            prev_hash: self.last_hash.clone(),
        };

        // 1. Calculate Hash
        // We hash the JSON representation to ensure integrity of the *content*
        let serialized = serde_json::to_string(&event).expect("Serialization failed");
        let hash = Self::calculate_hash(&serialized);

        // 2. Write to Disk (Append Only)
        // Format: HASH | JSON_PAYLOAD
        let entry = format!("{}|{}\n", hash, serialized);
        
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.file_path)?;
            
        file.write_all(entry.as_bytes())?;

        // 3. Update State
        self.last_hash = hash.clone();
        
        Ok(hash)
    }

    /// Verify the integrity of the entire log file.
    /// Recomputes all hashes from start to finish.
    /// Returns true if valid, false if tampered.
    pub fn verify_integrity(path: &str) -> bool {
        let path = Path::new(path);
        if !path.exists() {
            return true; // Empty is valid
        }

        let content = std::fs::read_to_string(path).unwrap_or_default();
        let mut expected_prev_hash = "0000000000000000000000000000000000000000000000000000000000000000".to_string();

        for line in content.lines() {
            if line.trim().is_empty() { continue; }
            
            // Split HASH | JSON
            let parts: Vec<&str> = line.splitn(2, '|').collect();
            if parts.len() != 2 { return false; } // Malformed line

            let recorded_hash = parts[0];
            let json_payload = parts[1];

            // 1. Check if payload claims correct prev_hash
            let event: AuditEvent = serde_json::from_str(json_payload).unwrap_or(AuditEvent {
                timestamp: 0, 
                principal: "".to_string(), 
                action: "".to_string(), 
                resource: "".to_string(), 
                details: "".to_string(), 
                prev_hash: "INVALID".to_string()
            });

            if event.prev_hash != expected_prev_hash {
                eprintln!("Chain Broken! Msg claims prev={}, but expected={}", event.prev_hash, expected_prev_hash);
                return false;
            }

            // 2. Re-hash payload and check against recorded hash
            let computed_hash = Self::calculate_hash(json_payload);
            if computed_hash != recorded_hash {
                eprintln!("Integrity Fail! content={}, computed={}, recorded={}", json_payload, computed_hash, recorded_hash);
                return false;
            }

            // Advance
            expected_prev_hash = recorded_hash.to_string();
        }

        true
    }

    fn calculate_hash(input: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(input);
        let result = hasher.finalize();
        hex::encode(result)
    }

    fn recover_last_hash(path: &str) -> std::io::Result<String> {
        // Read last valid line
        // Optimization: In prod, seek to end and read backward. Here, simple read_to_string is ok for now.
        if !Path::new(path).exists() {
             return Err(std::io::Error::new(std::io::ErrorKind::NotFound, "No file"));
        }
        
        let content = std::fs::read_to_string(path)?;
        let lines: Vec<&str> = content.lines().filter(|l| !l.trim().is_empty()).collect();
        
        if let Some(last) = lines.last() {
             let parts: Vec<&str> = last.splitn(2, '|').collect();
             if parts.len() >= 1 {
                 return Ok(parts[0].to_string());
             }
        }
        
        Err(std::io::Error::new(std::io::ErrorKind::NotFound, "Empty file"))
    }
}
