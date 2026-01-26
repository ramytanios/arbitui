# arbitui 📊

Terminal-based interest rate volatility arbitrage analysis tool.

**⚠️ Work in Progress**

## Features
- 📊 Terminal-based TUI for volatility cube analysis
- 🔄 Interactive arbitrage matrix visualization
- 💹 Market data integration (LIBOR/swap rates)
- 📈 Volatility smile and probability density charts

## Usage
```bash
# Start server
just run-server

# Start client (in another terminal)
just run-tui
```

## Architecture
- 🖥️ **Server**: WebSocket server with SQLite persistence, communicates via JSON RPC with [rates-vanilla-scope](https://github.com/ramytanios/rates-vanilla-scope)
- 💻 **Client**: [Textual](https://github.com/Textualize/textual) TUI with interactive data visualization
