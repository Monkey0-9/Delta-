use pyo3::prelude::*;
use crossbeam::queue::SegQueue;
use std::sync::Arc;
use std::time::{Instant, Duration};
use parking_lot::RwLock;
use std::collections::HashMap;
use chrono::{DateTime, Utc};

#[pyclass]
#[derive(Clone)]
pub enum EventType {
    MARKET_DATA = 0,
    ORDER = 1,
    FILL = 2,
    TIMER = 3,
    SYSTEM = 4,
    CUSTOM = 5,
}

#[pyclass]
#[derive(Clone)]
pub struct Event {
    #[pyo3(get, set)]
    event_id: String,
    #[pyo3(get, set)]
    event_type: EventType,
    #[pyo3(get, set)]
    timestamp: DateTime<Utc>,
    #[pyo3(get, set)]
    symbol: String,
    #[pyo3(get, set)]
    metadata: HashMap<String, String>,
}

#[pymethods]
impl Event {
    #[new]
    fn new(
        event_id: String,
        event_type: EventType,
        timestamp: DateTime<Utc>,
        symbol: String,
        metadata: HashMap<String, String>,
    ) -> Self {
        Event {
            event_id,
            event_type,
            timestamp,
            symbol,
            metadata,
        }
    }
}

#[pyclass]
pub struct EventQueue {
    queue: Arc<SegQueue<Event>>,
    handlers: Arc<RwLock<HashMap<EventType, Vec<PyObject>>>>,
}

#[pymethods]
impl EventQueue {
    #[new]
    fn new() -> Self {
        EventQueue {
            queue: Arc::new(SegQueue::new()),
            handlers: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    fn enqueue(&self, event: Event) {
        self.queue.push(event);
    }

    fn dequeue(&self) -> Option<Event> {
        self.queue.pop()
    }

    fn peek(&self) -> Option<Event> {
        // SegQueue doesn't support peek, we'll return None
        None
    }

    fn size(&self) -> usize {
        self.queue.len()
    }

    fn clear(&self) {
        while self.queue.pop().is_some() {}
    }

    fn process_next(&self, py: Python) -> PyResult<bool> {
        if let Some(event) = self.dequeue() {
            let handlers = self.handlers.read();
            if let Some(handler_list) = handlers.get(&event.event_type) {
                for handler in handler_list {
                    handler.call1(py, (event.clone(),))?;
                }
            }
            Ok(true)
        } else {
            Ok(false)
        }
    }

    fn process_all(&self, py: Python) -> PyResult<usize> {
        let mut count = 0;
        while self.process_next(py)? {
            count += 1;
        }
        Ok(count)
    }

    fn register_handler(&self, event_type: EventType, handler: PyObject) {
        let mut handlers = self.handlers.write();
        handlers.entry(event_type).or_insert_with(Vec::new).push(handler);
    }
}

#[pyclass]
pub struct RustBenchmark {
    operations: u64,
    start_time: Option<Instant>,
}

#[pymethods]
impl RustBenchmark {
    #[new]
    fn new() -> Self {
        RustBenchmark {
            operations: 0,
            start_time: None,
        }
    }

    fn start(&mut self) {
        self.start_time = Some(Instant::now());
        self.operations = 0;
    }

    fn stop(&mut self) -> f64 {
        if let Some(start) = self.start_time {
            let duration = start.elapsed();
            let ops_per_second = if duration.as_secs_f64() > 0.0 {
                self.operations as f64 / duration.as_secs_f64()
            } else {
                0.0
            };
            return ops_per_second;
        }
        0.0
    }

    fn benchmark_order_book(&mut self, iterations: u64) -> f64 {
        self.start();
        
        for _ in 0..iterations {
            // Simulate order book operations
            let mut bids: Vec<(f64, f64)> = Vec::with_capacity(100);
            let mut asks: Vec<(f64, f64)> = Vec::with_capacity(100);
            
            // Add orders
            for i in 0..100 {
                bids.push((150.0 - i as f64 * 0.01, 1000.0));
                asks.push((150.0 + i as f64 * 0.01, 1000.0));
            }
            
            // Sort (simulating price-time priority)
            bids.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap());
            asks.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
            
            self.operations += 1;
        }
        
        self.stop()
    }

    fn benchmark_event_queue(&mut self, iterations: u64) -> f64 {
        self.start();
        
        let queue = Arc::new(SegQueue::new());
        
        for _ in 0..iterations {
            // Enqueue
            let event = Event {
                event_id: "test".to_string(),
                event_type: EventType::MARKET_DATA,
                timestamp: Utc::now(),
                symbol: "AAPL".to_string(),
                metadata: HashMap::new(),
            };
            queue.push(event);
            
            // Dequeue
            let _ = queue.pop();
            
            self.operations += 1;
        }
        
        self.stop()
    }
}

#[pymodule]
fn delta_rust(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<EventType>()?;
    m.add_class::<Event>()?;
    m.add_class::<EventQueue>()?;
    m.add_class::<RustBenchmark>()?;
    Ok(())
}