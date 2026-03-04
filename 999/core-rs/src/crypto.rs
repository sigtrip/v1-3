use pyo3::prelude::*;
use rand::Rng;

#[pyfunction]
pub fn gen_key() -> PyResult<String> {
    let key: [u8; 32] = rand::thread_rng().gen();
    Ok(hex::encode(key))
}
