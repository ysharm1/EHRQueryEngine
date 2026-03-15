# Research Dataset Builder - Frontend

A Next.js 14 application for generating structured datasets from multimodal research data using natural language queries.

## Features

- **Authentication**: JWT-based authentication with session management and automatic token refresh
- **Natural Language Queries**: Submit research questions in plain English
- **Dataset Explorer**: Preview datasets with pagination, view metadata and schema
- **Export Interface**: Download datasets in CSV, Parquet, or JSON formats
- **Query Provenance**: Complete tracking of query execution and data sources

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS 4
- **State Management**: TanStack Query (React Query)
- **HTTP Client**: Axios
- **Authentication**: JWT with automatic refresh

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Backend API running at `http://localhost:8000`

### Installation

1. Install dependencies:
```bash
npm install
```

2. Configure environment variables:
```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

3. Run the development server:
```bash
npm run dev
```

4. Open [http://localhost:3000](http://localhost:3000) in your browser

## Project Structure

```
frontend/
├── app/                      # Next.js app directory
│   ├── dashboard/           # Main dashboard page
│   ├── login/               # Login page
│   ├── layout.tsx           # Root layout with providers
│   └── page.tsx             # Home page (redirects)
├── components/              # React components
│   ├── chat-interface.tsx   # Natural language query input
│   ├── dataset-explorer.tsx # Dataset preview and metadata
│   ├── dataset-export.tsx   # Export interface
│   └── protected-route.tsx  # Authentication wrapper
├── lib/                     # Utilities and contexts
│   ├── api-client.ts        # Axios instance with interceptors
│   ├── auth-context.tsx     # Authentication context
│   └── query-provider.tsx   # React Query provider
└── types/                   # TypeScript type definitions
    └── index.ts             # Shared types
```

## Key Components

### ChatInterface
- Natural language query input with textarea
- Query submission to backend API
- Display of parsed intent and confidence score
- Handling of clarification requests for low-confidence queries

### DatasetExplorer
- Dataset preview with pagination (20 rows per page)
- Metadata display (row count, column count, data sources)
- Schema information table
- Query provenance (original query, executed SQL, execution time)

### DatasetExport
- Export format selection (CSV, Parquet, JSON)
- Progress indicator during export generation
- Download links for generated files
- File size information

### Authentication
- Login page with username/password form
- JWT token storage in localStorage
- Automatic token refresh on 401 responses
- 30-minute session timeout with activity tracking
- Protected routes that redirect to login

## API Integration

The frontend communicates with the backend API at the following endpoints:

- `POST /api/auth/login` - User authentication
- `POST /api/auth/logout` - User logout
- `POST /api/auth/refresh` - Token refresh
- `GET /api/auth/me` - Get current user info
- `POST /api/query` - Submit natural language query
- `GET /api/dataset/{id}` - Get dataset metadata and preview
- `GET /api/dataset/{id}/download` - Download dataset files

## Authentication Flow

1. User submits credentials on login page
2. Backend returns access token, refresh token, and user info
3. Tokens stored in localStorage
4. Access token added to all API requests via interceptor
5. On 401 response, refresh token used to get new access token
6. Session expires after 30 minutes of inactivity
7. User redirected to login on session expiration

## Development

### Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint

### Code Style

- TypeScript strict mode enabled
- ESLint with Next.js configuration
- Tailwind CSS for styling
- React Server Components where possible
- Client Components marked with 'use client'

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API base URL | `http://localhost:8000` |

## Security Considerations

- JWT tokens stored in localStorage (consider httpOnly cookies for production)
- Automatic token refresh on expiration
- Session timeout after 30 minutes of inactivity
- Protected routes require authentication
- CORS configured on backend for frontend origin

## Future Enhancements

- Add dataset history/saved queries
- Implement real-time query progress updates via WebSocket
- Add data visualization components
- Support for collaborative dataset sharing
- Advanced query builder UI
- Dataset comparison tools

## License

This project is part of the Research Dataset Builder system.
