"""
Integration tests for health endpoint.
"""

import pytest
from unittest.mock import patch, Mock


class TestHealthEndpoint:
    """Test cases for health check endpoint."""

    @pytest.mark.integration
    def test_health_check_all_services_healthy(self, client):
        """Test health check when all services are healthy."""
        with patch('src.main.engine') as mock_engine, \
             patch('src.main.supabase') as mock_supabase, \
             patch('redis.Redis') as mock_redis_class, \
             patch('src.services.embeddings_service.EmbeddingsService') as mock_embeddings_class:

            # Mock database connection
            mock_conn = Mock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn

            # Mock Supabase
            mock_supabase.auth.get_session.return_value = {"access_token": "test"}

            # Mock Redis
            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_redis_class.return_value = mock_redis

            # Mock embeddings service
            mock_embeddings = Mock()
            mock_embeddings.test_connection.return_value = True
            mock_embeddings_class.return_value = mock_embeddings

            response = client.get("/api/health")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "healthy"
            assert data["services"]["database"] is True
            assert data["services"]["supabase"] is True
            assert data["services"]["redis"] is True
            assert data["services"]["embeddings"] is True
            assert "version" in data
            assert "environment" in data
            assert "uptime_seconds" in data
            assert "timestamp" in data

    @pytest.mark.integration
    def test_health_check_database_unhealthy(self, client):
        """Test health check when database is unhealthy."""
        with patch('src.main.engine') as mock_engine, \
             patch('src.main.supabase') as mock_supabase, \
             patch('redis.Redis') as mock_redis_class, \
             patch('src.services.embeddings_service.EmbeddingsService') as mock_embeddings_class:

            # Mock database connection failure
            mock_engine.connect.side_effect = Exception("Database connection failed")

            # Mock other services as healthy
            mock_supabase.auth.get_session.return_value = {"access_token": "test"}

            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_redis_class.return_value = mock_redis

            mock_embeddings = Mock()
            mock_embeddings.test_connection.return_value = True
            mock_embeddings_class.return_value = mock_embeddings

            response = client.get("/api/health")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "degraded"
            assert data["services"]["database"] is False
            assert data["services"]["supabase"] is True
            assert data["services"]["redis"] is True
            assert data["services"]["embeddings"] is True

    @pytest.mark.integration
    def test_health_check_supabase_unhealthy(self, client):
        """Test health check when Supabase is unhealthy."""
        with patch('src.main.engine') as mock_engine, \
             patch('src.main.supabase') as mock_supabase, \
             patch('redis.Redis') as mock_redis_class, \
             patch('src.services.embeddings_service.EmbeddingsService') as mock_embeddings_class:

            # Mock services
            mock_conn = Mock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn

            # Mock Supabase failure
            mock_supabase.auth.get_session.side_effect = Exception("Supabase connection failed")

            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_redis_class.return_value = mock_redis

            mock_embeddings = Mock()
            mock_embeddings.test_connection.return_value = True
            mock_embeddings_class.return_value = mock_embeddings

            response = client.get("/api/health")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "degraded"
            assert data["services"]["database"] is True
            assert data["services"]["supabase"] is False

    @pytest.mark.integration
    def test_health_check_redis_unhealthy(self, client):
        """Test health check when Redis is unhealthy."""
        with patch('src.main.engine') as mock_engine, \
             patch('src.main.supabase') as mock_supabase, \
             patch('redis.Redis') as mock_redis_class, \
             patch('src.services.embeddings_service.EmbeddingsService') as mock_embeddings_class:

            # Mock services
            mock_conn = Mock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn

            mock_supabase.auth.get_session.return_value = {"access_token": "test"}

            # Mock Redis failure
            mock_redis = Mock()
            mock_redis.ping.side_effect = Exception("Redis connection failed")
            mock_redis_class.return_value = mock_redis

            mock_embeddings = Mock()
            mock_embeddings.test_connection.return_value = True
            mock_embeddings_class.return_value = mock_embeddings

            response = client.get("/api/health")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "degraded"
            assert data["services"]["redis"] is False

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_health_check_embeddings_unhealthy(self, client):
        """Test health check when embeddings service is unhealthy."""
        with patch('src.main.engine') as mock_engine, \
             patch('src.main.supabase') as mock_supabase, \
             patch('redis.Redis') as mock_redis_class, \
             patch('src.services.embeddings_service.EmbeddingsService') as mock_embeddings_class:

            # Mock services
            mock_conn = Mock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn

            mock_supabase.auth.get_session.return_value = {"access_token": "test"}

            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_redis_class.return_value = mock_redis

            # Mock embeddings failure
            mock_embeddings = Mock()
            mock_embeddings.test_connection.return_value = False
            mock_embeddings_class.return_value = mock_embeddings

            response = client.get("/api/health")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "degraded"
            assert data["services"]["embeddings"] is False

    @pytest.mark.integration
    def test_health_check_multiple_services_unhealthy(self, client):
        """Test health check when multiple services are unhealthy."""
        with patch('src.main.engine') as mock_engine, \
             patch('src.main.supabase') as mock_supabase, \
             patch('redis.Redis') as mock_redis_class, \
             patch('src.services.embeddings_service.EmbeddingsService') as mock_embeddings_class:

            # Mock all services as failing
            mock_engine.connect.side_effect = Exception("Database failed")
            mock_supabase.auth.get_session.side_effect = Exception("Supabase failed")

            mock_redis = Mock()
            mock_redis.ping.side_effect = Exception("Redis failed")
            mock_redis_class.return_value = mock_redis

            mock_embeddings = Mock()
            mock_embeddings.test_connection.return_value = False
            mock_embeddings_class.return_value = mock_embeddings

            response = client.get("/api/health")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "degraded"
            assert data["services"]["database"] is False
            assert data["services"]["supabase"] is False
            assert data["services"]["redis"] is False
            assert data["services"]["embeddings"] is False

    @pytest.mark.integration
    def test_health_check_response_format(self, client):
        """Test that health check response has correct format."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()

        # Required fields
        required_fields = [
            "status", "version", "environment", "services",
            "uptime_seconds", "timestamp"
        ]
        for field in required_fields:
            assert field in data

        # Services field should be a dict
        assert isinstance(data["services"], dict)

        # Status should be valid
        assert data["status"] in ["healthy", "degraded"]

        # Uptime should be numeric
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0