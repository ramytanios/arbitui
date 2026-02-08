# arbitui 📊

Terminal-based interest rates volatility arbitrage analysis tool.

**⚠️ Work in Progress**

## Features

- Terminal-based rates volatility cube analysis
- Interactive arbitrage matrix visualization
- Volatility smile and market implied probability density charts

## Future Features

- **Volatility Adjustment**: Ability to adjust volatilities to fix arbitrageable tenors/expiries.

## Demo 

<img alt="Demo" src="demo.gif" width="2048" height="1024" />

## Usage

```bash
# Start server
just run-server

# Start client
just run-tui
```

## Architecture

- **Server**: WebSocket server with SQLite persistence that communicates with the client and bridges to [rates-scope](https://github.com/ramytanios/rates-scope) via JSON-RPC over a Unix domain socket.

- **Client**: [Textual](https://github.com/Textualize/textual)-based TUI that connects over WebSocket for interactive data visualization.

