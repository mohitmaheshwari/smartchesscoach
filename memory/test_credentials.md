# Test Credentials

## Dev Mode (Emergent Preview Only)
- Set `DEV_MODE=true` in `backend/.env` to enable dev user fallback
- Dev user ID: `dev_user_local`
- No password needed — auto-authenticates when no session exists

## Production (User's Server)
- Google OAuth login via `bhutramohit@gmail.com` (super_admin)
- Auth handled via Google OAuth flow in `routes/auth.py`

## Test Data
- Test game ID: `test_game_a793ed92` (Italian Game, White lost)
- Test game ID: `test_game_dc1e2a28` (Scotch Game, White won)
- Both in DB `test_database` under user_id `dev_user_local`
