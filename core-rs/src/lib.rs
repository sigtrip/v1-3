use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use regex::Regex;

#[derive(Serialize, Deserialize)]
pub enum SafetyLevel {
    Safe,
    Warning,
    Critical,
}

#[pyclass]
pub struct EmpathyEngine {
    hard_constraints: Vec<String>,
}

#[pymethods]
impl EmpathyEngine {
    #[new]
    pub fn new() -> Self {
        EmpathyEngine {
            hard_constraints: vec![
                r"os\.remove\(".to_string(),
                r"shutil\.rmtree\(".to_string(),
                r"socket\.send".to_string(),
                r"requests\.post".to_string(),
                r"gpio\.cleanup".to_string(),
                r"power_off".to_string(),
                r"execute_arbitrary_code".to_string(),
            ],
        }
    }

    pub fn analyze_intent(&self, task_description: &str, generated_code: &str) -> PyResult<(String, String)> {
        for pattern in &self.hard_constraints {
            let re = Regex::new(pattern).unwrap();
            if re.is_match(generated_code) {
                return Ok(("critical".to_string(), format!("Обнаружена опасная операция: {}", pattern)));
            }
        }
        // TODO: Семантический анализ через LLM (вызывать из Python)
        Ok(("safe".to_string(), "Проверка пройдена".to_string()))
    }
}

#[pymodule]
fn empathy_engine(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<EmpathyEngine>()?;
    Ok(())
}
