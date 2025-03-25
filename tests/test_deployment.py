"""
Integration tests for deployment.

This module tests the deployment configuration and container setup.
"""
import os
import pytest
import docker
import requests
import time
import socket
import subprocess
from typing import Dict, List, Any, Tuple
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Skip these tests by default (only run them explicitly)
pytestmark = pytest.mark.skip(reason="Deployment tests should be run manually")


class TestDockerCompose:
    """Tests for Docker Compose setup."""
    
    @classmethod
    def setup_class(cls):
        """Set up the Docker client."""
        cls.client = docker.from_env()
        cls.project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.compose_file = os.path.join(cls.project_dir, "config", "docker-compose.yml")
    
    def test_compose_file_exists(self):
        """Test if the docker-compose file exists."""
        assert os.path.isfile(self.compose_file), f"Docker Compose file not found at {self.compose_file}"
    
    def test_dockerfile_exists(self):
        """Test if the Dockerfile exists."""
        dockerfile_path = os.path.join(self.project_dir, "config", "Dockerfile")
        assert os.path.isfile(dockerfile_path), f"Dockerfile not found at {dockerfile_path}"
    
    def run_compose_up(self) -> Tuple[int, str, str]:
        """Run docker-compose up and return its output."""
        process = subprocess.Popen(
            ["docker-compose", "-f", self.compose_file, "up", "-d"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.project_dir
        )
        stdout, stderr = process.communicate()
        return process.returncode, stdout.decode('utf-8'), stderr.decode('utf-8')
    
    def run_compose_down(self) -> Tuple[int, str, str]:
        """Run docker-compose down and return its output."""
        process = subprocess.Popen(
            ["docker-compose", "-f", self.compose_file, "down"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.project_dir
        )
        stdout, stderr = process.communicate()
        return process.returncode, stdout.decode('utf-8'), stderr.decode('utf-8')
    
    def test_compose_up_down(self):
        """Test that docker-compose up and down commands work."""
        # First, ensure everything is down
        self.run_compose_down()
        
        # Try to bring up the containers
        returncode, stdout, stderr = self.run_compose_up()
        assert returncode == 0, f"docker-compose up failed with stderr: {stderr}"
        
        # Wait for containers to be up
        time.sleep(10)
        
        # Verify the app container is running
        containers = self.client.containers.list()
        container_names = [c.name for c in containers]
        assert "kairoslms-app" in container_names, "App container not running"
        assert "kairoslms-db" in container_names, "Database container not running"
        
        # Tear down the containers
        returncode, stdout, stderr = self.run_compose_down()
        assert returncode == 0, f"docker-compose down failed with stderr: {stderr}"


class TestNetworkConnectivity:
    """Tests for network connectivity between containers."""
    
    @classmethod
    def setup_class(cls):
        """Set up the Docker client and start containers."""
        cls.client = docker.from_env()
        cls.project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.compose_file = os.path.join(cls.project_dir, "config", "docker-compose.yml")
        
        # Run docker-compose up
        process = subprocess.Popen(
            ["docker-compose", "-f", cls.compose_file, "up", "-d"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cls.project_dir
        )
        process.communicate()
        
        # Wait for containers to start
        time.sleep(10)
    
    @classmethod
    def teardown_class(cls):
        """Stop containers after tests."""
        # Run docker-compose down
        process = subprocess.Popen(
            ["docker-compose", "-f", cls.compose_file, "down"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cls.project_dir
        )
        process.communicate()
    
    def get_container(self, name: str):
        """Get a container by name."""
        containers = self.client.containers.list()
        for container in containers:
            if container.name == name:
                return container
        return None
    
    def test_app_db_connectivity(self):
        """Test connectivity between app and database containers."""
        # Get the app container
        app_container = self.get_container("kairoslms-app")
        assert app_container is not None, "App container not found"
        
        # Run a command to test the DB connection
        exit_code, output = app_container.exec_run(
            "python -c \"import os; from sqlalchemy import create_engine; from sqlalchemy.sql import text; \
            engine = create_engine(f'postgresql://{os.environ.get(\"DB_USER\")}:{os.environ.get(\"DB_PASSWORD\")}@{os.environ.get(\"DB_HOST\")}:{os.environ.get(\"DB_PORT\")}/{os.environ.get(\"DB_NAME\")}'); \
            with engine.connect() as conn: result = conn.execute(text('SELECT 1')); print(result.fetchone()[0])\""
        )
        
        assert exit_code == 0, f"Database connection test failed with output: {output.decode('utf-8')}"
        assert "1" in output.decode('utf-8'), "Expected query result not found"


class TestAPIEndpoints:
    """Tests for API endpoints in the running application."""
    
    @classmethod
    def setup_class(cls):
        """Set up the Docker client and start containers."""
        cls.client = docker.from_env()
        cls.project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.compose_file = os.path.join(cls.project_dir, "config", "docker-compose.yml")
        
        # Run docker-compose up
        process = subprocess.Popen(
            ["docker-compose", "-f", cls.compose_file, "up", "-d"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cls.project_dir
        )
        process.communicate()
        
        # Wait for containers to start and API to be available
        cls.api_url = "http://localhost:8000"
        cls.wait_for_api()
    
    @classmethod
    def teardown_class(cls):
        """Stop containers after tests."""
        # Run docker-compose down
        process = subprocess.Popen(
            ["docker-compose", "-f", cls.compose_file, "down"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cls.project_dir
        )
        process.communicate()
    
    @classmethod
    def wait_for_api(cls, timeout=30):
        """Wait for the API to become available."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{cls.api_url}/health", timeout=1)
                if response.status_code == 200:
                    logger.info("API is available")
                    return
            except (requests.RequestException, socket.error):
                pass
            
            time.sleep(1)
        
        raise TimeoutError(f"API did not become available within {timeout} seconds")
    
    def test_health_endpoint(self):
        """Test the health check endpoint."""
        response = requests.get(f"{self.api_url}/health")
        assert response.status_code == 200, f"Health check failed with status code {response.status_code}"
        assert response.json()["status"] == "healthy", "Health check returned unexpected response"
    
    def test_api_endpoints(self):
        """Test key API endpoints."""
        # Test API docs
        response = requests.get(f"{self.api_url}/docs")
        assert response.status_code == 200, f"API docs not available, got status code {response.status_code}"
        
        # Test main HTML routes
        response = requests.get(self.api_url)
        assert response.status_code == 200, f"Main page not available, got status code {response.status_code}"
        
        response = requests.get(f"{self.api_url}/chat")
        assert response.status_code == 200, f"Chat page not available, got status code {response.status_code}"
        
        response = requests.get(f"{self.api_url}/settings")
        assert response.status_code == 200, f"Settings page not available, got status code {response.status_code}"


class TestContainerResources:
    """Tests for container resource usage."""
    
    @classmethod
    def setup_class(cls):
        """Set up the Docker client and start containers."""
        cls.client = docker.from_env()
        cls.project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.compose_file = os.path.join(cls.project_dir, "config", "docker-compose.yml")
        
        # Run docker-compose up
        process = subprocess.Popen(
            ["docker-compose", "-f", cls.compose_file, "up", "-d"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cls.project_dir
        )
        process.communicate()
        
        # Wait for containers to start
        time.sleep(10)
    
    @classmethod
    def teardown_class(cls):
        """Stop containers after tests."""
        # Run docker-compose down
        process = subprocess.Popen(
            ["docker-compose", "-f", cls.compose_file, "down"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cls.project_dir
        )
        process.communicate()
    
    def get_container(self, name: str):
        """Get a container by name."""
        containers = self.client.containers.list()
        for container in containers:
            if container.name == name:
                return container
        return None
    
    def test_container_resources(self):
        """Test container resource usage."""
        # Get the app container
        app_container = self.get_container("kairoslms-app")
        assert app_container is not None, "App container not found"
        
        # Get container stats
        stats = app_container.stats(stream=False)
        
        # Check CPU usage is reasonable
        # Note: This is just a basic check and may need adjustments based on your app
        cpu_usage = stats["cpu_stats"]["cpu_usage"]["total_usage"]
        cpu_system_usage = stats["cpu_stats"]["system_cpu_usage"]
        if cpu_system_usage > 0:
            cpu_percent = (cpu_usage / cpu_system_usage) * 100.0
            logger.info(f"App container CPU usage: {cpu_percent:.2f}%")
            assert cpu_percent < 80, f"CPU usage too high: {cpu_percent:.2f}%"
        
        # Check memory usage is reasonable
        memory_usage = stats["memory_stats"].get("usage", 0)
        memory_limit = stats["memory_stats"].get("limit", 1)
        memory_percent = (memory_usage / memory_limit) * 100.0
        logger.info(f"App container memory usage: {memory_percent:.2f}% ({memory_usage / (1024 * 1024):.2f} MB)")
        assert memory_percent < 80, f"Memory usage too high: {memory_percent:.2f}%"


class TestBackupFunctionality:
    """Tests for database backup functionality."""
    
    @classmethod
    def setup_class(cls):
        """Set up the Docker client and start containers."""
        cls.client = docker.from_env()
        cls.project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.compose_file = os.path.join(cls.project_dir, "config", "docker-compose.yml")
        
        # Create .env file with backup enabled
        env_content = """
        # Database Settings
        DB_USER=postgres
        DB_PASSWORD=postgres
        DB_NAME=kairoslms
        DB_HOST=db
        DB_PORT=5432
        
        # Backup Settings
        ENABLE_BACKUPS=true
        BACKUP_ON_SHUTDOWN=true
        DB_BACKUP_INTERVAL_DAYS=1
        KEEP_BACKUPS_DAYS=7
        """
        
        env_path = os.path.join(cls.project_dir, "config", ".env.test")
        with open(env_path, "w") as f:
            f.write(env_content)
        
        # Run docker-compose up with custom env file
        process = subprocess.Popen(
            ["docker-compose", "-f", cls.compose_file, "--env-file", env_path, "up", "-d"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cls.project_dir
        )
        process.communicate()
        
        # Wait for containers to start
        time.sleep(10)
    
    @classmethod
    def teardown_class(cls):
        """Stop containers after tests."""
        # Run docker-compose down
        process = subprocess.Popen(
            ["docker-compose", "-f", cls.compose_file, "down"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cls.project_dir
        )
        process.communicate()
        
        # Clean up test env file
        env_path = os.path.join(cls.project_dir, "config", ".env.test")
        if os.path.exists(env_path):
            os.remove(env_path)
    
    def get_container(self, name: str):
        """Get a container by name."""
        containers = self.client.containers.list()
        for container in containers:
            if container.name == name:
                return container
        return None
    
    def test_backup_directory_exists(self):
        """Test that the backup directory exists and is accessible."""
        # Get the app container
        app_container = self.get_container("kairoslms-app")
        assert app_container is not None, "App container not found"
        
        # Check if backup directory exists
        exit_code, output = app_container.exec_run("python -c \"import os; print(os.path.exists('/app/backups'))\"")
        assert exit_code == 0, f"Backup directory check failed with output: {output.decode('utf-8')}"
        assert "True" in output.decode('utf-8'), "Backup directory not found"
    
    def test_manual_backup(self):
        """Test manual backup functionality."""
        # Get the app container
        app_container = self.get_container("kairoslms-app")
        assert app_container is not None, "App container not found"
        
        # Run a manual backup
        exit_code, output = app_container.exec_run(
            "python -c \"from src.utils.backup import backup_database; import os; connection_string = f'postgresql://{os.environ.get(\"DB_USER\")}:{os.environ.get(\"DB_PASSWORD\")}@{os.environ.get(\"DB_HOST\")}:{os.environ.get(\"DB_PORT\")}/{os.environ.get(\"DB_NAME\")}'; success, path = backup_database(connection_string); print(f'Success: {success}, Path: {path}')\""
        )
        
        assert exit_code == 0, f"Manual backup failed with output: {output.decode('utf-8')}"
        assert "Success: True" in output.decode('utf-8'), "Backup was not successful"
        
        # Verify backup file exists
        backup_file = output.decode('utf-8').split("Path: ")[1].split("\n")[0].strip()
        exit_code, output = app_container.exec_run(f"ls -l {backup_file}")
        assert exit_code == 0, f"Backup file check failed with output: {output.decode('utf-8')}"
        assert "No such file" not in output.decode('utf-8'), "Backup file not found"