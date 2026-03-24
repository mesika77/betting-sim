-- Migration: add commence_time column to bets table
ALTER TABLE bets ADD COLUMN IF NOT EXISTS commence_time TIMESTAMPTZ;
