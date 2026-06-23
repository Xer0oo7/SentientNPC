# Contributing to SentientNPC

Thank you for your interest in contributing! This document provides guidelines for working with the project.

## Development Setup

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Dashboard
```bash
cd dashboard
npm install
```

## Code Quality

### Backend
- **Type Hints**: Use type hints in all function signatures for better IDE support and type checking.
- **Tests**: Run tests with `py -3 -m pytest` (Windows) or `python -m pytest` (Unix).
- **Logging**: Use the `logging` module with appropriate levels (DEBUG, INFO, WARNING, ERROR).

### Dashboard
- **Linting**: Run `npm run lint` to check code with ESLint.
- **Formatting**: Run `npm run format` to automatically format code with Prettier.
- **React Best Practices**: Use functional components with hooks, avoid prop drilling, and keep components focused.

## Project Structure

```
├── backend/               # FastAPI backend + SQLite
│   ├── routers/          # API endpoints
│   ├── tests/            # Unit tests
│   └── requirements.txt   # Python dependencies
├── dashboard/            # React + Vite frontend
│   ├── src/
│   │   ├── components/   # Reusable React components
│   │   ├── pages/        # Page-level components
│   │   └── api/          # API client
│   └── package.json      # Node dependencies
└── docs/                 # Documentation
```

## Making Changes

1. **Create a feature branch**: `git checkout -b feature/your-feature`
2. **Make focused changes**: Keep commits atomic and well-described.
3. **Test your changes**: 
   - Backend: `python -m pytest`
   - Dashboard: `npm run lint`
4. **Update documentation**: If adding new features, update relevant docs.
5. **Submit a PR**: Include a clear description of what changed and why.

## Common Tasks

### Adding a New API Endpoint
1. Create or update a router in `backend/routers/`
2. Define request/response models in `backend/models.py`
3. Add the router to `backend/main.py`
4. Test with `pytest` and verify in Swagger docs (`/docs`)

### Adding a New Dashboard Component
1. Create the component in `backend/components/`
2. Define API calls in `backend/api/client.js`
3. Import and use in a page component
4. Test locally with `npm run dev`
5. Lint with `npm run lint`

### Running the Full Stack
```bash
docker-compose up --build
```
This starts the backend on port 8000 and requires the dashboard to be run separately:
```bash
cd dashboard && npm run dev  # Port 5173
```

## Questions?

- Check existing documentation in `docs/`
- Review related code and tests
- Open an issue for bugs or feature requests

Happy coding! 🚀
