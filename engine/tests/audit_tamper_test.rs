use engine::audit::AuditLogger;
use std::fs;

#[test]
fn test_audit_integrity() {
    let test_file = "test_audit.log";
    // Cleanup previous runs
    if std::path::Path::new(test_file).exists() {
        fs::remove_file(test_file).unwrap();
    }

    let mut logger = AuditLogger::new(test_file);

    // 1. Write legitimate events
    logger.log("admin", "DEPLOY_ALGO", "System", "v1.0.0").unwrap();
    logger.log("trader1", "MARKET_BUY", "BTC-USD", "1.5 BTC").unwrap();
    
    // 2. Verify Integrity (Should Pass)
    assert!(AuditLogger::verify_integrity(test_file), "Initial integrity check failed");

    // 3. TAMPERING SIMULATION
    // We open the file and modify the "1.5 BTC" to "100.0 BTC" without updating the hash
    let content = fs::read_to_string(test_file).unwrap();
    let tampered_content = content.replace("1.5 BTC", "100.0 BTC"); // Fraud!
    fs::write(test_file, tampered_content).unwrap();

    // 4. Verify Integrity (Should Fail)
    assert!(!AuditLogger::verify_integrity(test_file), "Tampering was NOT detected!");
    
    // Cleanup
    fs::remove_file(test_file).unwrap();
}
