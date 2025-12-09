"""Hashcash token generation using Node.js or Deno helper."""
import asyncio
import logging
import subprocess
import json
import os
import shutil
from pathlib import Path
from typing import Optional, Literal

logger = logging.getLogger(__name__)


class HashcashGenerator:
    """Generates hashcash tokens for proof-of-work using Node.js or Deno helper."""
    
    _hashcash_js_path: Optional[Path] = None
    _runtime: Optional[Literal['deno', 'node']] = None
    
    @staticmethod
    def _detect_runtime() -> Optional[Literal['deno', 'node']]:
        """Detect which JavaScript runtime is available (Deno or Node.js)."""
        if HashcashGenerator._runtime is not None:
            logger.debug(f"Using cached runtime: {HashcashGenerator._runtime}")
            return HashcashGenerator._runtime
        
        logger.info("Detecting JavaScript runtime for hashcash generation...")
        
        # Check for Deno first
        if shutil.which('deno'):
            HashcashGenerator._runtime = 'deno'
            logger.info("Detected Deno runtime - will use Deno for hashcash generation")
            return 'deno'
        
        # Check for Node.js
        if shutil.which('node'):
            HashcashGenerator._runtime = 'node'
            logger.info("Detected Node.js runtime - will use Node.js for hashcash generation")
            return 'node'
        
        HashcashGenerator._runtime = None
        logger.warning("Neither Deno nor Node.js found - hashcash generation will fail")
        return None
    
    @staticmethod
    def _get_hashcash_runner_path() -> Path:
        """Get path to hashcash_runner.js helper file."""
        if HashcashGenerator._hashcash_js_path is None:
            # Get the directory where this file is located
            current_file = Path(__file__)
            # Go up: core/crypto/hashing -> core/crypto -> core -> megapy -> helpers
            megapy_dir = current_file.parent.parent.parent.parent
            HashcashGenerator._hashcash_js_path = megapy_dir / "helpers" / "hashcash_runner.js"
        return HashcashGenerator._hashcash_js_path
    
    @staticmethod
    async def generate(challenge: str) -> str:
        """
        Generates a hashcash token for the given challenge using Deno or Node.js.
        
        Args:
            challenge: Header value from X-Hashcash (format: "1:y:timestamp:token")
            
        Returns:
            Hashcash solution in format "1:token:prefix" where prefix is base64-encoded 4 bytes
        """
        import time
        start_time = time.time()
        
        logger.debug(f"Starting hashcash generation for challenge: {challenge[:50]}...")
        
        runtime = HashcashGenerator._detect_runtime()
        if runtime is None:
            logger.error("No JavaScript runtime available for hashcash generation")
            raise RuntimeError("Neither Deno nor Node.js found. Please install Deno or Node.js to use hashcash generation.")
        
        hashcash_runner = HashcashGenerator._get_hashcash_runner_path()
        
        if not hashcash_runner.exists():
            logger.error(f"hashcash_runner.js not found at {hashcash_runner}")
            raise FileNotFoundError(f"hashcash_runner.js not found at {hashcash_runner}")
        
        logger.debug(f"Using {runtime} to execute {hashcash_runner}")
        
        # Execute script with detected runtime
        try:
            if runtime == 'deno':
                # Deno command: deno run --allow-all script.js args
                logger.debug(f"Executing: deno run --allow-all {hashcash_runner} <challenge>")
                process = await asyncio.create_subprocess_exec(
                    'deno',
                    'run',
                    '--allow-all',
                    str(hashcash_runner),
                    challenge,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=hashcash_runner.parent
                )
            else:  # node
                # Node.js command: node script.js args
                logger.debug(f"Executing: node {hashcash_runner} <challenge>")
                process = await asyncio.create_subprocess_exec(
                    'node',
                    str(hashcash_runner),
                    challenge,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=hashcash_runner.parent
                )
            
            logger.debug(f"Waiting for {runtime} process to complete...")
            stdout, stderr = await process.communicate()
            elapsed = (time.time() - start_time) * 1000
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "Unknown error"
                logger.error(f"{runtime} execution failed (return code {process.returncode}): {error_msg}")
                raise RuntimeError(f"{runtime} execution failed: {error_msg}")
            
            # Parse JSON output
            output = stdout.decode('utf-8').strip()
            logger.debug(f"{runtime} output: {output[:100]}...")
            
            try:
                result = json.loads(output)
                if result.get('success'):
                    solution = result['result']
                    logger.info(f"Hashcash generation successful using {runtime} (took {elapsed:.2f}ms): {solution}")
                    return solution
                else:
                    error_msg = result.get('error', 'Unknown error')
                    logger.error(f"Hashcash generation failed: {error_msg}")
                    raise RuntimeError(f"Hashcash generation failed: {error_msg}")
            except json.JSONDecodeError as e:
                # If not JSON, try to parse as plain text
                output = output.strip()
                if output:
                    logger.warning(f"Received non-JSON output from {runtime}, treating as plain text: {output[:100]}")
                    logger.info(f"Hashcash generation completed using {runtime} (took {elapsed:.2f}ms)")
                    return output
                logger.error(f"Invalid JSON output from {runtime}: {output}")
                raise RuntimeError(f"Invalid output from {runtime}: {output}")
                
        except FileNotFoundError:
            logger.error(f"{runtime} executable not found in PATH")
            raise RuntimeError(f"{runtime} not found. Please install {runtime} to use hashcash generation.")
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"Error executing {runtime} hashcash (took {elapsed:.2f}ms): {e}", exc_info=True)
            raise
    
    @staticmethod
    def generate_sync(challenge: str) -> str:
        """
        Synchronous version of generate (for backward compatibility).
        Uses asyncio.run internally.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, we need to use a different approach
                # Create a new event loop in a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: asyncio.run(HashcashGenerator.generate(challenge))
                    )
                    return future.result()
            else:
                return loop.run_until_complete(HashcashGenerator.generate(challenge))
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(HashcashGenerator.generate(challenge))
