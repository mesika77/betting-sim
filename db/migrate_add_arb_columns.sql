-- Migration: add arb_group_id and bookmaker columns to bets table
-- Run this in the Neon SQL Editor at console.neon.tech

ALTER TABLE bets ADD COLUMN IF NOT EXISTS arb_group_id UUID;
ALTER TABLE bets ADD COLUMN IF NOT EXISTS bookmaker TEXT;

CREATE INDEX IF NOT EXISTS idx_bets_arb_group ON bets(arb_group_id);
