use zed_extension_api::{self as zed, Result};

struct CarbonExtension {
    cached_binary_path: Option<String>,
}

// We embed the python script so we can run it with `python -c`
// This avoids needing to locate the script file at runtime.
const CARBON_LSP_CODE: &str = include_str!("../carbon_bundled.py");

impl CarbonExtension {
    fn language_server_binary_path(
        &mut self,
        _language_server_id: &zed::LanguageServerId,
        worktree: &zed::Worktree,
    ) -> Result<String> {
        if let Some(path) = &self.cached_binary_path {
            return Ok(path.clone());
        }

        if let Some(path) = worktree.which("python3") {
            self.cached_binary_path = Some(path.clone());
            return Ok(path);
        }

        if let Some(path) = worktree.which("python") {
            self.cached_binary_path = Some(path.clone());
            return Ok(path);
        }

        Err("Python 3 is required but not found in your PATH.".into())
    }
}

impl zed::Extension for CarbonExtension {
    fn new() -> Self {
        Self {
            cached_binary_path: None,
        }
    }

    fn language_server_command(
        &mut self,
        language_server_id: &zed::LanguageServerId,
        worktree: &zed::Worktree,
    ) -> Result<zed::Command> {
        let python_path = self.language_server_binary_path(language_server_id, worktree)?;

        Ok(zed::Command {
            command: python_path,
            args: vec![
                "-c".to_string(),
                CARBON_LSP_CODE.to_string(),
            ],
            env: Default::default(),
        })
    }
}

zed::register_extension!(CarbonExtension);
