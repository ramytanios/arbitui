from textual.theme import Theme

rates_terminal_theme = Theme(
    name="rates-terminal",
    primary="#00ff9c",  # accent green (focus, active)
    secondary="#6f7894",  # muted secondary text
    accent="#00ff9c",  # same as primary, disciplined use
    foreground="#e6eaf2",  # main text
    background="#161b26",  # screen background
    success="#00ff9c",
    warning="#f5c97a",
    error="#ff6b6b",
    surface="#1c2230",  # tables / cards
    panel="#20263a",  # headers / panels
    dark=True,
    variables={
        # Cursor & selection
        "block-cursor-text-style": "none",
        "input-selection-background": "#00ff9c 30%",
        "input-cursor-background": "#00ff9c",
        # Footer / key hints
        "footer-key-foreground": "#00ff9c",
        "footer-key-background": "#161b26",
        # Borders & focus
        "focus-ring": "#00ff9c",
        "panel-border": "#2a324a",
        # Tables
        "datatable-background": "#1c2230",
        "datatable-header-background": "#20263a",
        "datatable-row-hover": "#242c40",
        # Inputs
        "input-background": "#141926",
        "input-border": "#2a324a",
        "input-border-focus": "#00ff9c",
        # Scrollbars
        "scrollbar-background": "#161b26",
        "scrollbar-color": "#2a324a",
        "scrollbar-color-hover": "#3a4463",
    },
)
