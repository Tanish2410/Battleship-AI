#!/usr/bin/env python3
"""
Code Clash Battleship Bot Challenge - CREATE UofT - Winter 2026

YOUR CUSTOM BATTLESHIP BOT STRATEGY
Override the strategy methods below to implement your bot.

===========================================
IMPORTANT:
===========================================
- DO NOT modify battleship_api.py
- ONLY override the 3 strategy methods below
- Use helper methods (starting with _) from the API
- Test your bot with bot_validator.py before submission

Have fun!
"""

import random
from typing import Dict, List, Set, Tuple
from battleship_api import BattleshipBotAPI, run_bot, BOARD_SIZE, SHIP_SIZES


class MyBattleshipBot(BattleshipBotAPI):

    # INITIALIZATION
    
    def __init__(self):
        super().__init__()
        self.remaining_ships = list(SHIP_SIZES.keys())
        self.blocked_cells: Dict[Tuple[int, int], int] = {}  
        self.current_turn = 0

    # ABILITIES

    def ability_selection(self):
        return ["HS", "RF"]

    # SHIP PLACEMENT

    def place_ship_strategy(self, ship_name, game_state):

        # Preset placements
        preset = {
            "ship_1x4": {"cell": [6, 2], "direction": "H"},
            "ship_1x3": {"cell": [5, 0], "direction": "V"},
            "ship_2x3": {"cell": [3, 4], "direction": "H"},
            "ship_1x2": {"cell": [0, 6], "direction": "V"},
        }

        placed = self._get_placed_coordinates(game_state)

        # Try preset placement first
        if ship_name in preset:
            cell = preset[ship_name]["cell"]
            direction = preset[ship_name]["direction"]

            cells = self._get_ship_cells(ship_name, cell[0], cell[1], direction)
            if cells and self._is_valid_placement(cells, placed):
                return {
                    "placement": {
                        "name": ship_name,
                        "cell": cell,
                        "direction": direction
                    }
                }

        # Fall back
        rnd = self._get_random_placement(ship_name, placed)
        if rnd is not None:
            return {"placement": rnd}

        # Ultimate fallback
        return {
            "placement": {
                "name": ship_name,
                "cell": [0, 0],
                "direction": "H"
            }
        }

    # COMBAT
    def combat_strategy(self, game_state):

        # Update turn count
        self.current_turn += 1

        # Get current opponent grid and abilities
        grid = self._get_opponent_grid(game_state)
        abilities = self._get_available_abilities(game_state)

        # Track blocked cells
        self._track_blocked_cells(grid)

        # Update remaining ships based on sunk ships
        self._update_remaining_ships(game_state)

        # Use Hailstorm immediately
        if "HS" in abilities:
            return {
                "combat": {
                    "cell": [0, 0],
                    "ability": {"HS": {}}
                }
            }

        # Use RF right away if two good targets exist
        if "RF" in abilities:
            targets = self._rf_targets(grid)
            if len(targets) >= 2:
                (r1, c1), (r2, c2) = targets[0], targets[1]
                return {
                    "combat": {
                        "cell": [0, 0],
                        "ability": {"RF": [[r1, c1], [r2, c2]]}
                    }
                }

        # Finish off hit clusters
        clusters = self._find_hit_clusters(grid)
        if clusters:

            # Prioritize clusters closest to sinking
            cluster = min(clusters, key=lambda c: self._estimate_remaining_hits(c, grid))
            targets = self._cluster_targets(cluster, grid)

            # If any targets found, shoot the first one
            if targets:
                r, c = targets[0]
                return {
                    "combat": {
                        "cell": [r, c],
                        "ability": {"None": {}}
                    }
                }

        # Blocked cell retry
        retry_target = self._get_retry_blocked_cell()
        if retry_target:
            r, c = retry_target
            return {
                "combat": {
                    "cell": [r, c],
                    "ability": {"None": {}}
                }
            }

        # Probability-based hunting
        prob_map = self._calculate_probability_map(grid)
        best_cell = self._get_highest_probability_cell(prob_map, grid)

        # If a best cell found, shoot there
        if best_cell:
            r, c = best_cell
            return {
                "combat": {
                    "cell": [r, c],
                    "ability": {"None": {}}
                }
            }

        # Fallback
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if grid[r][c] == "N":
                    return {
                        "combat": {
                            "cell": [r, c],
                            "ability": {"None": {}}
                        }
                    }

        # Ultimate fallback
        return {
            "combat": {
                "cell": [0, 0],
                "ability": {"None": {}}
            }
        }

    # HELPERS

    # Estimate remaining hits needed to sink ships in a cluster
    def _estimate_remaining_hits(self, cluster, grid):

        rows = [r for r, _ in cluster]
        cols = [c for _, c in cluster]
        cluster_size = len(cluster)

        # Check against remaining ships
        for ship_name in self.remaining_ships:
            ship_rows, ship_cols = SHIP_SIZES[ship_name]
            ship_length = max(ship_rows, ship_cols)

            if cluster_size >= ship_length:
                return 0

            if len(set(rows)) == 1 or len(set(cols)) == 1:
                return ship_length - cluster_size

        return 4 - cluster_size

    # Track blocked cells
    def _track_blocked_cells(self, grid):
        
        # Add newly blocked cells
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if grid[r][c] == "B" and (r, c) not in self.blocked_cells:
                    self.blocked_cells[(r, c)] = self.current_turn

    # Get a blocked cell ready to retry
    def _get_retry_blocked_cell(self):
        ready_cells = []
        for (r, c), blocked_turn in list(self.blocked_cells.items()):
            
            # Shield lasts 2 turns, wait 3+ to be safe
            if self.current_turn - blocked_turn >= 3:
                ready_cells.append((r, c))
                del self.blocked_cells[(r, c)]

        return ready_cells[0] if ready_cells else None

    # Remove sunk ships from remaining ship list
    def _update_remaining_ships(self, game_state):

        # Check opponent ships for sunk status
        for ship in game_state.get("opponent_ships", []):
            if isinstance(ship, dict):
                ship_name = ship.get("name", "")
                is_sunk = ship.get("sunk", False)
                if is_sunk and ship_name in self.remaining_ships:
                    self.remaining_ships.remove(ship_name)

    # Calculate probability map
    def _calculate_probability_map(self, grid):

        # Initialize probability map
        prob_map = [[0.0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]

        # For each remaining ship, simulate placements
        for ship_name in self.remaining_ships:
            rows, cols = SHIP_SIZES[ship_name]
            ship_length = max(rows, cols)
            weight = 1.0 / float(ship_length)  

            # Horizontal placements
            for r in range(BOARD_SIZE):
                for c in range(BOARD_SIZE - cols + 1):
                    if self._can_place_ship(grid, r, c, rows, cols, "H"):
                        for dc in range(cols):
                            for dr in range(rows):
                                prob_map[r + dr][c + dc] += weight

            # Vertical placements
            for r in range(BOARD_SIZE - cols + 1):
                for c in range(BOARD_SIZE):
                    if self._can_place_ship(grid, r, c, rows, cols, "V"):
                        for dc in range(cols):
                            for dr in range(rows):
                                prob_map[r + dc][c + dr] += weight

        return prob_map

    # Check if ship can be placed at position
    def _can_place_ship(self, grid, start_r, start_c, rows, cols, orientation):

        # Check bounds and existing hits/misses
        if orientation == "H":
            for c in range(cols):
                for r in range(rows):
                    nr, nc = start_r + r, start_c + c
                    if nr >= BOARD_SIZE or nc >= BOARD_SIZE:
                        return False
                    if grid[nr][nc] in ["M", "S", "B"]:
                        return False
                    
        # Vertical
        else:
            for c in range(cols):
                for r in range(rows):
                    nr, nc = start_r + c, start_c + r
                    if nr >= BOARD_SIZE or nc >= BOARD_SIZE:
                        return False
                    if grid[nr][nc] in ["M", "S", "B"]:
                        return False
        return True

    # Get highest probability cell
    def _get_highest_probability_cell(self, prob_map, grid):

        # Find cell(s) with max probability
        max_prob = 0.0
        best_cells: List[Tuple[int, int]] = []

        # Check if all remaining ships are even-sized
        even_only = bool(self.remaining_ships) and all(
            (max(SHIP_SIZES[s]) % 2 == 0) for s in self.remaining_ships
        )

        # Identify best cells
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if grid[r][c] == "N":
                    p = prob_map[r][c]
                    if p > max_prob:
                        max_prob = p
                        best_cells = [(r, c)]
                    elif p == max_prob and p > 0:
                        best_cells.append((r, c))

        # No valid cells found
        if not best_cells:
            return None

        # If even-only, filter to even parity cells
        if even_only:
            parity_cells = [(r, c) for r, c in best_cells if (r + c) % 2 == 0]

            # If any parity cells exist, use them
            if parity_cells:
                best_cells = parity_cells

        # Tie-breaker: prefer cells with more unshot neighbours and centrality
        def neighbour_score(rc: Tuple[int, int]) -> int:
            r, c = rc
            score = 0

            # Count unshot neighbours
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and grid[nr][nc] == "N":
                    score += 1
            return score

        # Sort best cells by neighbour score and centrality
        best_cells.sort(
            key=lambda rc: (
                neighbour_score(rc),
                -abs(rc[0] - BOARD_SIZE // 2) - abs(rc[1] - BOARD_SIZE // 2),
            ),
            reverse=True
        )
        return best_cells[0]

    """
    Choose two RF targets optimally.

    Priority:
    1) Extend sinkable hit clusters (endpoints first).
    2) If only one such target exists, pair with best hunt cell.
    3) Retry soon-to-expire blocked cells.
    4) Two highest-probability hunt cells.
    """
    def _rf_targets(self, grid):
        
        # Find hit clusters
        clusters = self._find_hit_clusters(grid)
        if clusters:
            clusters.sort(key=lambda c: self._estimate_remaining_hits(c, grid))
            picks: List[Tuple[int, int]] = []
            seen: Set[Tuple[int, int]] = set()

            # Target cluster endpoints first
            for cl in clusters:
                for t in self._cluster_targets(cl, grid):
                    if t not in seen:
                        picks.append(t)
                        seen.add(t)
                    if len(picks) == 2:
                        return picks

            # If only one pick so far, try to add best hunt cell
            if len(picks) == 1:
                prob_map = self._calculate_probability_map(grid)
                extra = self._get_n_highest_probability_cells(prob_map, grid, 1)
                if extra:
                    e = extra[0]
                    if e not in seen:
                        picks.append(e)
                return picks

        # Retry blocked cells if any ready
        ready_blocked = []
        for (r, c), blocked_turn in list(self.blocked_cells.items()):
            if self.current_turn - blocked_turn >= 3:
                ready_blocked.append((r, c))
                if len(ready_blocked) == 2:
                    return ready_blocked

        # Fall back to two highest-probability hunt cells
        prob_map = self._calculate_probability_map(grid)
        return self._get_n_highest_probability_cells(prob_map, grid, 2)

    # Get N highest probability cells
    def _get_n_highest_probability_cells(self, prob_map, grid, n):
        cells_with_prob = []
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if grid[r][c] == "N" and prob_map[r][c] > 0:
                    cells_with_prob.append((r, c, prob_map[r][c]))
        cells_with_prob.sort(key=lambda x: x[2], reverse=True)
        return [(r, c) for r, c, _ in cells_with_prob[:n]]

    # Find clusters of hits on the grid
    def _find_hit_clusters(self, grid):
        hits = [(r, c) for r in range(BOARD_SIZE)
                for c in range(BOARD_SIZE) if grid[r][c] == "H"]
        hit_set = set(hits)
        visited: Set[Tuple[int, int]] = set()
        clusters: List[List[Tuple[int, int]]] = []

        for h in hits:
            if h in visited:
                continue
            stack = [h]
            visited.add(h)
            cluster = []

            while stack:
                r, c = stack.pop()
                cluster.append((r, c))
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nxt = (r + dr, c + dc)
                    if nxt in hit_set and nxt not in visited:
                        visited.add(nxt)
                        stack.append(nxt)

            clusters.append(cluster)

        return clusters

    # Cluster target selection
    def _cluster_targets(self, cluster, grid):
        rows = [r for r, _ in cluster]
        cols = [c for _, c in cluster]

        if len(cluster) == 1:
            r, c = cluster[0]
            candidates = [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]
        elif len(set(rows)) == 1:
            row = rows[0]
            candidates = [(row, min(cols) - 1), (row, max(cols) + 1)]
        else:
            col = cols[0]
            candidates = [(min(rows) - 1, col), (max(rows) + 1, col)]

        return [
            (r, c) for r, c in candidates
            if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and grid[r][c] == "N"
        ]


if __name__ == "__main__":
    run_bot(MyBattleshipBot)
