#!/usr/bin/env python3
import asyncio
import os
import signal
import logging

# --- CONFIGURATION ---
AUDIO_INPUT = "alsa_input.usb-0d8c_USB_Sound_Device-00.analog-stereo"
STREAM_PORT = 8888
LOG_FILE = "/config/ffmpeg_minidisc.log"
PID_FILE = "/config/scripts/minidisc_stream.pid"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

clients = set()
running = True

async def handle_client(reader, writer):
    """Handles each incoming HTTP client asynchronously."""
    addr = writer.get_extra_info('peername')
    client_ip = addr[0] if addr else "Unknown"
    logging.info(f"New client connected: {client_ip}")

    # Read and discard incoming HTTP request headers
    try:
        await reader.readuntil(b"\r\n\r\n")
    except Exception:
        pass

    # Send HTTP response headers
    header = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: audio/mpeg\r\n"
        "Cache-Control: no-cache, no-store, must-revalidate\r\n"
        "Pragma: no-cache\r\n"
        "Expires: 0\r\n"
        "Connection: close\r\n\r\n"
    )

    try:
        writer.write(header.encode('utf-8'))
        await writer.drain()
        clients.add(writer)

        # Keep connection open until client disconnects or service stops
        while running and not writer.is_closing():
            await asyncio.sleep(1)

    except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
        pass
    finally:
        clients.discard(writer)
        if not writer.is_closing():
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
        logging.info(f"Client disconnected: {client_ip}")

async def broadcast_stream():
    """Continuously reads FFmpeg output and broadcasts audio chunks to all connected clients."""
    global running

    cmd = [
        "ffmpeg",
        "-threads", "1",
        "-f", "pulse",
        "-i", AUDIO_INPUT,
        "-acodec", "libmp3lame",
        "-b:a", "256k",
        "-ac", "2",
        "-ar", "44100",
        "-f", "mp3",
        "pipe:1"
    ]

    while running:
        logging.info("Starting FFmpeg process...")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )

        try:
            while running and process.returncode is None:
                # Read small chunks from FFmpeg stdout
                chunk = await process.stdout.read(4096)
                if not chunk:
                    break

                # Broadcast data chunk to all connected clients in parallel
                if clients:
                    disconnected = set()
                    for writer in list(clients):
                        try:
                            writer.write(chunk)
                            # Non-blocking drain with timeout ensures slow clients
                            # won't block the main broadcast loop
                            await asyncio.wait_for(writer.drain(), timeout=0.5)
                        except Exception:
                            disconnected.add(writer)

                    # Clean up disconnected or stalled clients
                    for writer in disconnected:
                        clients.discard(writer)
                        if not writer.is_closing():
                            writer.close()

        except Exception as e:
            logging.error(f"Error in stream loop: {e}")

        # If FFmpeg exits unexpectedly, clean up process handles
        if process.returncode is None:
            try:
                process.terminate()
                await asyncio.sleep(0.5)
                if process.returncode is None:
                    process.kill()
            except Exception:
                pass

        if running:
            logging.warning("FFmpeg process terminated. Restarting in 2 seconds...")
            await asyncio.sleep(2)

async def main():
    global running

    # Write process ID to PID file
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    # Register OS signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))

    # Start HTTP stream server on specified port
    server = await asyncio.start_server(handle_client, '0.0.0.0', STREAM_PORT)
    logging.info(f"AsyncIO web server started on port {STREAM_PORT}")

    # Start FFmpeg stream broadcast task
    broadcast_task = asyncio.create_task(broadcast_stream())

    async with server:
        try:
            await server.serve_forever()
        except asyncio.CancelledError:
            pass

    # Clean up tasks and PID file on shutdown
    broadcast_task.cancel()
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    logging.info("Stream manager shut down cleanly.")

async def shutdown():
    global running
    logging.info("Termination signal received. Stopping server...")
    running = False

    # Close all active client connections
    for writer in list(clients):
        if not writer.is_closing():
            writer.close()

    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
