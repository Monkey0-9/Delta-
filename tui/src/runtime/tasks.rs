//! Asynchronous background task tracking for DELTA TUI.
//!
//! Section 14:
//! Shows running, queued, completed, failed, and cancelled tasks with progress indicators.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TaskStatus {
    Queued,
    Running,
    Completed,
    Failed,
    Cancelled,
}

impl TaskStatus {
    pub fn badge(&self) -> &'static str {
        match self {
            Self::Queued => "[QUEUED]",
            Self::Running => "[RUNNING]",
            Self::Completed => "[COMPLETED]",
            Self::Failed => "[FAILED]",
            Self::Cancelled => "[CANCELLED]",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AsyncTask {
    pub id: String,
    pub name: String,
    pub category: String, // "Research", "Backtest", "Inference", "Data", "Risk"
    pub status: TaskStatus,
    pub progress: f32, // 0.0 to 1.0
    pub started_at: String,
    pub details: String,
}

#[derive(Debug, Clone, Default)]
pub struct TaskManager {
    pub tasks: Vec<AsyncTask>,
}

impl TaskManager {
    pub fn new() -> Self {
        Self { tasks: Vec::new() }
    }

    pub fn add_task(&mut self, id: String, name: String, category: String, details: String) {
        let now = chrono::Utc::now().format("%H:%M:%S").to_string();
        self.tasks.retain(|t| t.id != id);
        self.tasks.push(AsyncTask {
            id,
            name,
            category,
            status: TaskStatus::Running,
            progress: 0.0,
            started_at: now,
            details,
        });
    }

    pub fn update_progress(&mut self, id: &str, progress: f32) {
        if let Some(task) = self.tasks.iter_mut().find(|t| t.id == id) {
            task.progress = progress.clamp(0.0, 1.0);
        }
    }

    pub fn complete_task(&mut self, id: &str, success: bool, message: String) {
        if let Some(task) = self.tasks.iter_mut().find(|t| t.id == id) {
            task.status = if success {
                TaskStatus::Completed
            } else {
                TaskStatus::Failed
            };
            task.progress = 1.0;
            task.details = message;
        }
    }

    pub fn cancel_task(&mut self, id: &str) {
        if let Some(task) = self.tasks.iter_mut().find(|t| t.id == id) {
            task.status = TaskStatus::Cancelled;
        }
    }

    pub fn active_count(&self) -> usize {
        self.tasks
            .iter()
            .filter(|t| t.status == TaskStatus::Running || t.status == TaskStatus::Queued)
            .count()
    }
}
