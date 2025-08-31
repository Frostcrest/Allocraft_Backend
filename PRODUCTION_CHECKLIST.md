# Allocraft Production Deployment Checklist

## 🏗️ Backend Deployment

### Database Migration
- [ ] Run migration script: `python migrate_production.py`
- [ ] Verify all tables exist (check script output)
- [ ] Set `DATABASE_URL` environment variable if using external database

### Environment Variables
- [ ] `DATABASE_URL` - Database connection string
- [ ] `SECRET_KEY` - JWT secret key for authentication
- [ ] `SCHWAB_CLIENT_ID` - Schwab API client ID
- [ ] `SCHWAB_CLIENT_SECRET` - Schwab API client secret
- [ ] `SCHWAB_REDIRECT_URI` - OAuth redirect URI
- [ ] Any other API keys (TwelveData, etc.)

### Dependencies
- [ ] All packages from `requirements.txt` installed
- [ ] Python 3.11+ available
- [ ] FastAPI/Uvicorn configured

## 🎨 Frontend Deployment

### Build Configuration
- [ ] Set `VITE_API_BASE_URL` to production backend URL
- [ ] Run `npm run build` to create production bundle
- [ ] Verify build artifacts in `dist/` directory

### Environment Variables
- [ ] `VITE_API_BASE_URL` - Backend API URL (e.g., https://api.allocraft.com)

## 🔄 New Features Implemented

### ✅ Persistent Schwab Storage System
- **Database Models**: `SchwabAccount`, `SchwabPosition`, `PositionSnapshot`
- **Sync Service**: Automated position synchronization with change tracking
- **API Endpoints**: `/schwab/positions`, `/schwab/sync`, `/schwab/sync-status`
- **Frontend Integration**: Updated `Stocks.tsx` with "Sync Fresh Data" functionality

### 🎯 Key Benefits
1. **Performance**: No more waiting for API calls - positions cached in database
2. **Reliability**: Historical position snapshots for tracking changes
3. **Efficiency**: Smart sync only updates changed positions
4. **User Experience**: "Sync Fresh Data" button for manual refreshes

## 🧪 Testing Checklist

### Backend Testing
- [ ] Health check: `GET /` returns status
- [ ] Schwab endpoints: `GET /schwab/positions`
- [ ] Database connectivity verified
- [ ] All existing features still work

### Frontend Testing  
- [ ] Navigate to Stocks page
- [ ] Click "Sync Fresh Data" button
- [ ] Verify positions load from database
- [ ] Test all existing functionality

## 📊 Database Schema

### New Tables Created
```sql
schwab_accounts
├── id (Primary Key)
├── account_hash (Unique)
├── account_number
├── type
├── created_at
└── updated_at

schwab_positions  
├── id (Primary Key)
├── account_id (Foreign Key)
├── instrument_cusip
├── instrument_symbol
├── quantity
├── market_value
├── average_price
├── created_at
└── updated_at

position_snapshots
├── id (Primary Key) 
├── account_id (Foreign Key)
├── total_positions
├── total_market_value
├── snapshot_at
├── created_at
└── updated_at
```

## 🚀 Deployment Commands

### Backend (Render/Railway/etc.)
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python migrate_production.py

# Start server
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Frontend (Vercel/Netlify/etc.)
```bash
# Install dependencies
npm install

# Build for production
npm run build

# Serve static files from dist/
```

## 🔍 Monitoring

### Key Metrics to Watch
- [ ] Database connection health
- [ ] Schwab API rate limits
- [ ] Position sync frequency
- [ ] User authentication flows
- [ ] Frontend load times

## 📝 Notes

- The migration script is safe to run multiple times
- Existing data will not be affected
- The sync service runs automatically when positions are requested
- Users can manually sync using the "Sync Fresh Data" button
- Historical position data is preserved in snapshots
