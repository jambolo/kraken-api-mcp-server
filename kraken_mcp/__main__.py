def main() -> None:
    from .server import create_server
    mcp = create_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
