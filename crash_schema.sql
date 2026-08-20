-- ============================================
-- CRASH GAME SCHEMA
-- Copy and run this in your PostgreSQL database
-- ============================================

-- Crash game rounds
CREATE TABLE IF NOT EXISTS crash_games (
    id SERIAL PRIMARY KEY,
    round_number BIGINT UNIQUE NOT NULL,
    crash_point DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, live, crashed, completed
    betting_window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    betting_window_end TIMESTAMP,
    game_start_time TIMESTAMP,
    crash_time TIMESTAMP,
    seed VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT check_crash_point CHECK (crash_point >= 2.00 AND crash_point <= 500.00)
);

-- Individual bets placed on crash games
CREATE TABLE IF NOT EXISTS crash_bets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_id INTEGER NOT NULL REFERENCES crash_games(id) ON DELETE CASCADE,
    bet_amount DECIMAL(12, 2) NOT NULL,
    cashout_multiplier DECIMAL(10, 2),
    cashout_at DECIMAL(10, 2),
    payout_amount DECIMAL(12, 2),
    status VARCHAR(20) DEFAULT 'active', -- active, cashed_out, lost, won
    is_auto_cashout BOOLEAN DEFAULT FALSE,
    placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cashed_out_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT check_bet_amount CHECK (bet_amount >= 10 AND bet_amount <= 10000),
    CONSTRAINT check_cashout_mult CHECK (cashout_multiplier IS NULL OR (cashout_multiplier >= 1.01 AND cashout_multiplier <= 500)),
    UNIQUE(user_id, game_id)
);

-- User crash game statistics
CREATE TABLE IF NOT EXISTS crash_stats (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    total_bets INTEGER DEFAULT 0,
    total_wagered DECIMAL(15, 2) DEFAULT 0,
    total_winnings DECIMAL(15, 2) DEFAULT 0,
    total_losses DECIMAL(15, 2) DEFAULT 0,
    win_count INTEGER DEFAULT 0,
    loss_count INTEGER DEFAULT 0,
    biggest_win DECIMAL(15, 2) DEFAULT 0,
    best_multiplier DECIMAL(10, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_crash_games_status ON crash_games(status);
CREATE INDEX IF NOT EXISTS idx_crash_games_created ON crash_games(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_crash_bets_user ON crash_bets(user_id);
CREATE INDEX IF NOT EXISTS idx_crash_bets_game ON crash_bets(game_id);
CREATE INDEX IF NOT EXISTS idx_crash_bets_status ON crash_bets(status);
CREATE INDEX IF NOT EXISTS idx_crash_bets_user_game ON crash_bets(user_id, game_id);
