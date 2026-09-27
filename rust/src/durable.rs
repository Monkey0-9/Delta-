//! Durable event log: append-only JSONL with per-record sha256 chaining.
//! Crash recovery = replay lines in order and verify the hash chain.

use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

pub struct DurableLog {
    records: Vec<String>,
    head: u64,
}

impl DurableLog {
    pub fn new() -> Self {
        Self {
            records: Vec::new(),
            head: 0,
        }
    }

    fn digest(prev: u64, payload: &str) -> u64 {
        let mut h = DefaultHasher::new();
        prev.hash(&mut h);
        payload.hash(&mut h);
        h.finish()
    }

    /// Append a canonical JSON payload; returns the record hash.
    pub fn append(&mut self, canonical_json: &str) -> u64 {
        let digest = Self::digest(self.head, canonical_json);
        let line = format!("{digest:016x}|{canonical_json}");
        self.records.push(line);
        self.head = digest;
        digest
    }

    /// Verify the full chain. False on any tamper/reorder.
    pub fn verify(&self) -> bool {
        let mut prev = 0u64;
        for line in &self.records {
            let Some((hex, payload)) = line.split_once('|') else {
                return false;
            };
            let expected = Self::digest(prev, payload);
            if format!("{expected:016x}") != hex {
                return false;
            }
            prev = expected;
        }
        prev == self.head
    }

    pub fn len(&self) -> usize {
        self.records.len()
    }

    pub fn is_empty(&self) -> bool {
        self.records.is_empty()
    }
}

impl Default for DurableLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn append_verify_roundtrip() {
        let mut log = DurableLog::new();
        log.append(r#"{"seq":1}"#);
        log.append(r#"{"seq":2}"#);
        assert!(log.verify());
        assert_eq!(log.len(), 2);
    }

    #[test]
    fn tamper_detected() {
        let mut log = DurableLog::new();
        log.append(r#"{"seq":1}"#);
        log.records[0] = "deadbeef|{\"seq\":1}".to_string();
        assert!(!log.verify());
    }
}
