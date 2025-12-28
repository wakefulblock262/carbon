mod sourcemap;
mod state;

use axum::{
    extract::State,
    routing::{get, post},
    Json, Router,
};
use clap::{Parser, Subcommand};
use state::{AppState, SyncCommand};
use tracing::{error, info, Level};
use tracing_subscriber::FmtSubscriber;

#[derive(Parser)]
#[command(author, version, about, long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
    Serve {
        #[arg(short, long, default_value_t = 8000)]
        port: u16,
    },

    Import,

    Export,

    Sourcemap,

    Lsp,

    InstallPlugin,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let subscriber = FmtSubscriber::builder()
        .with_max_level(Level::INFO)
        .finish();

    tracing::subscriber::set_global_default(subscriber).expect("setting default subscriber failed");

    let cli = Cli::parse();

    let port = 8000;

    match &cli.command {
        Some(Commands::Serve { port }) => {
            info!("Starting server on port {}", port);
            server(*port).await?;
        }
        Some(Commands::Import) => {
            info!("Triggering Import...");
            send_command_to_server(SyncCommand::Import, port).await?;
        }
        Some(Commands::Export) => {
            info!("Triggering Export...");
            send_command_to_server(SyncCommand::Export, port).await?;
        }
        Some(Commands::Sourcemap) => {
            info!("Generating sourcemap...");
            let cwd = std::env::current_dir()?;
            let json = sourcemap::generate_sourcemap(cwd)?;
            println!("{}", json);
        }
        Some(Commands::Lsp) => {
            info!("Starting LSP...");

            println!("Carbon LSP started (placeholder)");
            std::future::pending::<()>().await;
        }
        Some(Commands::InstallPlugin) => {
            info!("Installing Roblox Studio plugin...");
            install_plugin().await?;
        }
        None => {
            info!("Starting server on default port {}", port);
            server(port).await?;
        }
    }

    Ok(())
}

async fn server(port: u16) -> anyhow::Result<()> {
    use std::net::SocketAddr;

    let state = AppState::new();

    let app = Router::new()
        .route("/", get(root))
        .route("/poll", get(poll_command))
        .route("/command", post(receive_command))
        .route("/sync/update", post(sync_update))
        .with_state(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    info!("Listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

async fn root() -> Json<serde_json::Value> {
    Json(serde_json::json!({ "message": "Carbon Running" }))
}

async fn poll_command(State(state): State<AppState>) -> Json<serde_json::Value> {
    let cmd = state.pop_command();

    Json(serde_json::json!({ "command": cmd }))
}

async fn receive_command(
    State(state): State<AppState>,
    Json(payload): Json<SyncCommand>,
) -> Json<serde_json::Value> {
    info!("Received command request: {:?}", payload);
    state.set_command(payload);
    Json(serde_json::json!({ "success": true }))
}

async fn sync_update(Json(payload): Json<serde_json::Value>) -> Json<serde_json::Value> {
    info!("Received sync update from Roblox");

    if let Some(files) = payload.get("files").and_then(|f| f.as_array()) {
        for file in files {
            if let (Some(path_str), Some(content)) = (
                file.get("path").and_then(|p| p.as_str()),
                file.get("content").and_then(|c| c.as_str()),
            ) {
                if path_str.contains("..") {
                    error!("Skipping unsafe path: {}", path_str);
                    continue;
                }

                let path = std::path::Path::new(path_str);

                if let Some(parent) = path.parent() {
                    if let Err(e) = std::fs::create_dir_all(parent) {
                        error!("Failed to create directory {:?}: {}", parent, e);
                        continue;
                    }
                }

                if let Err(e) = std::fs::write(path, content) {
                    error!("Failed to write file {:?}: {}", path, e);
                } else {
                    info!("Imported: {:?}", path);
                }
            }
        }

        if let Ok(cwd) = std::env::current_dir() {
            match sourcemap::generate_sourcemap(cwd) {
                Ok(json) => {
                    if let Err(e) = std::fs::write("sourcemap.json", json) {
                        error!("Failed to write sourcemap.json: {}", e);
                    } else {
                        info!("Generated sourcemap.json");
                    }
                }
                Err(e) => error!("Failed to generate sourcemap: {}", e),
            }
        }
    }

    Json(serde_json::json!({ "success": true }))
}

async fn send_command_to_server(cmd: SyncCommand, port: u16) -> anyhow::Result<()> {
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::TcpStream;

    let body = serde_json::to_string(&cmd)?;
    let len = body.len();

    let request = format!(
        "POST /command HTTP/1.1\r\n\
         Host: 127.0.0.1:{}\r\n\
         Content-Type: application/json\r\n\
         Content-Length: {}\r\n\
         Connection: close\r\n\
         \r\n\
         {}",
        port, len, body
    );

    let addr = format!("127.0.0.1:{}", port);

    match TcpStream::connect(&addr).await {
        Ok(mut stream) => {
            stream.write_all(request.as_bytes()).await?;

            let mut response = String::new();

            stream.read_to_string(&mut response).await?;

            if response.contains("200 OK") {
                info!("Command sent successfully.");
            } else {
                error!("Server returned error or invalid response.");
                println!("Response: {}", response);
            }
        }
        Err(e) => {
            error!("Failed to connect to server at {}. Is it running?", addr);
            return Err(e.into());
        }
    }

    Ok(())
}

async fn install_plugin() -> anyhow::Result<()> {
    let token = std::env::var("GITHUB_TOKEN").ok();
    let mut headers = reqwest::header::HeaderMap::new();
    headers.insert(
        reqwest::header::USER_AGENT,
        reqwest::header::HeaderValue::from_static("carbon/2.0"),
    );
    headers.insert(
        reqwest::header::ACCEPT,
        reqwest::header::HeaderValue::from_static("application/vnd.github.v3+json"),
    );
    if let Some(ref t) = token {
        let auth_value = reqwest::header::HeaderValue::from_str(&format!("token {}", t))
            .map_err(|e| anyhow::anyhow!("Invalid GITHUB_TOKEN header: {}", e))?;
        headers.insert(reqwest::header::AUTHORIZATION, auth_value);
        info!("Using GITHUB_TOKEN for GitHub API requests");
    }

    let client = reqwest::Client::builder()
        .default_headers(headers)
        .build()?;
    let url = "https://api.github.com/repos/Proton-Interactive/carbon-plugin/releases/latest";

    info!("Fetching latest release from GitHub...");
    let response = client.get(url).send().await?;
    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        error!("Failed to fetch release: {} - {}", status, body);
        return Err(anyhow::anyhow!("Failed to fetch release: {}", status));
    }

    let release: serde_json::Value = response.json().await?;
    let assets = release
        .get("assets")
        .and_then(|a| a.as_array())
        .ok_or_else(|| anyhow::anyhow!("No assets found"))?;

    let plugin_asset = assets
        .iter()
        .find(|asset| {
            asset
                .get("name")
                .and_then(|n| n.as_str())
                .map_or(false, |name| name.ends_with(".rbxmx"))
        })
        .ok_or_else(|| anyhow::anyhow!("No .rbxmx asset found"))?;

    let download_url = plugin_asset
        .get("browser_download_url")
        .and_then(|u| u.as_str())
        .ok_or_else(|| anyhow::anyhow!("No download URL"))?;

    info!("Downloading plugin from {}", download_url);
    let plugin_response = client.get(download_url).send().await?;
    if !plugin_response.status().is_success() {
        let status = plugin_response.status();
        let body = plugin_response.text().await.unwrap_or_default();
        error!("Failed to download plugin: {} - {}", status, body);
        return Err(anyhow::anyhow!("Failed to download plugin: {}", status));
    }

    let plugin_data = plugin_response.bytes().await?;

    info!(
        "Detected OS: {}, Arch: {}",
        std::env::consts::OS,
        std::env::consts::ARCH
    );

    let plugins_dir = match std::env::consts::OS {
        "windows" => {
            let local_app_data = std::env::var("LOCALAPPDATA")?;
            std::path::Path::new(&local_app_data)
                .join("Roblox")
                .join("Plugins")
        }
        "macos" => {
            let home = std::env::var("HOME")?;
            let base_path = if std::env::consts::ARCH == "aarch64" {
                std::path::Path::new(&home)
                    .join("Library")
                    .join("Application Support")
            } else {
                std::path::Path::new(&home).join("Documents")
            };
            base_path.join("Roblox").join("Plugins")
        }
        _ => return Err(anyhow::anyhow!("Unsupported OS: {}", std::env::consts::OS)),
    };
    std::fs::create_dir_all(&plugins_dir)?;

    let plugin_path = plugins_dir.join("carbon.rbxmx");
    std::fs::write(&plugin_path, plugin_data)?;

    info!("Plugin installed to {:?}", plugin_path);
    Ok(())
}
