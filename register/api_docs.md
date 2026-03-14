# File Tracking System API Documentation

## Overview
The File Tracking System REST API provides programmatic access to all features of the file tracking system. It allows third-party applications to integrate with the system.

## Base URL
```
http://localhost:8000/register/api/
```

## Authentication
The API uses Django's session-based authentication. To authenticate:

1. **Login via API**: POST to `/login/` with `username` and `password`
2. **Session Cookie**: The API will return a session cookie that must be included in subsequent requests
3. **CSRF Token**: For POST/PUT/DELETE requests, include the CSRF token in the `X-CSRFToken` header

### Example Authentication Flow
```bash
# 1. Get CSRF token
curl -c cookies.txt -b cookies.txt http://localhost:8000/register/api/

# 2. Login
curl -c cookies.txt -b cookies.txt -X POST \
  -d "username=admin&password=yourpassword" \
  -H "X-CSRFToken: <token_from_response>" \
  http://localhost:8000/login/

# 3. Access API (with session)
curl -b cookies.txt http://localhost:8000/register/api/files/
```

## API Endpoints

### Status
- **GET** `/api/status/` - Check API status

### Dashboard
- **GET** `/api/dashboard/` - Get dashboard statistics

### Files
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/files/` | List all files |
| POST | `/api/files/` | Create new file |
| GET | `/api/files/{id}/` | Get file details |
| PUT | `/api/files/{id}/` | Update file |
| DELETE | `/api/files/{id}/` | Delete file |
| POST | `/api/files/{id}/checkout/` | Checkout file |
| POST | `/api/files/{id}/checkin/` | Checkin file |
| POST | `/api/files/{id}/archive/` | Archive file |
| POST | `/api/files/{id}/restore/` | Restore file |

### File Filters
- `?status=checked_out` - Filter by status
- `?department=1` - Filter by department
- `?priority=high` - Filter by priority
- `?search=keyword` - Search by title or reference

### Departments
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/departments/` | List all departments |
| POST | `/api/departments/` | Create department |
| GET | `/api/departments/{id}/` | Get department |
| PUT | `/api/departments/{id}/` | Update department |
| DELETE | `/api/departments/{id}/` | Delete department |

### File Requests
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/requests/` | List requests |
| POST | `/api/requests/` | Create request |
| GET | `/api/requests/{id}/` | Get request |
| POST | `/api/requests/{id}/approve/` | Approve request |
| POST | `/api/requests/{id}/reject/` | Reject request |
| POST | `/api/requests/{id}/mark_handed_over/` | Mark as handed over |
| POST | `/api/requests/{id}/confirm_receipt/` | Confirm receipt |

### Notifications
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/notifications/` | List notifications |
| POST | `/api/notifications/{id}/mark_read/` | Mark as read |
| POST | `/api/notifications/mark_all_read/` | Mark all as read |

### Activity Logs (Admin Only)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/activity/` | List activity logs |

### User Profiles
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profiles/` | List profiles |
| GET | `/api/profiles/me/` | Current user profile |

## Response Format

### Success Response
```json
{
  "count": 100,
  "next": "http://localhost:8000/register/api/files/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "reference": "HR/2026/0001",
      "title": "Employee Records",
      "status": "in_registry",
      "department": {
        "id": 1,
        "name": "Human Resources"
      }
    }
  ]
}
```

### Error Response
```json
{
  "error": "Detail error message"
}
```

## Example Usage

### List Files
```bash
curl -b cookies.txt http://localhost:8000/register/api/files/
```

### Create File Request
```bash
curl -b cookies.txt -X POST \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: <token>" \
  -d '{"file": 1, "purpose": "Need for audit"}' \
  http://localhost:8000/register/api/requests/
```

### Approve Request (Admin)
```bash
curl -b cookies.txt -X POST \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: <token>" \
  -d '{"pickup_date": "2026-03-20T10:00:00Z", "notes": "Approved"}' \
  http://localhost:8000/register/api/requests/1/approve/
```

## Permissions

| User Role | Access Level |
|-----------|--------------|
| Admin | Full access to all endpoints |
| Registry | Full access to files, requests, departments |
| Department User | Read-only access to files, can create requests |

## Rate Limiting
Currently not implemented. For production, consider adding throttling.
