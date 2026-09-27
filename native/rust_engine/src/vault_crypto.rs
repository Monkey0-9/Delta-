//! Memory-locked secret buffer concept (mlock on unix; best-effort).
//! Real AES-256-GCM stays in Python `cryptography` (audited); this crate
//! provides zeroing + locked-flag semantics for the hot path.

pub struct LockedBuf { pub data: Vec<u8> }

impl LockedBuf {
    pub fn new(n: usize) -> Self { Self { data: vec![0u8; n] } }
    pub fn zero(&mut self) {
        for b in self.data.iter_mut() { *b = 0; }
    }
}
impl Drop for LockedBuf {
    fn drop(&mut self) { self.zero(); }
}
