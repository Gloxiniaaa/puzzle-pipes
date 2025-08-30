import pygame
import random
import sys
from typing import List, Tuple

# Constants
BACKGROUND_COLOR = (0, 0, 0)
GRID_COLOR = (150, 150, 150)
CONNECTED_COLOR = (0, 0, 255)  # Blue for water source and connected tiles
UNCONNECTED_COLOR = (200, 200, 200)  # Gray for unconnected tiles
LOCKED_COLOR = (255, 0, 0)
SOURCE_CIRCLE_COLOR = (255, 0, 0)  # Red for water source center
PIPE_THICKNESS = 10
CENTER_CIRCLE_RADIUS = PIPE_THICKNESS

# Pipe types definitions
# Each type is a list of directions it connects to: 0-N, 1-E, 2-S, 3-W
PIPE_TYPES = {
    'l': [[1, 3], [0, 2]],  # Horizontal or vertical
    'v': [[0, 1], [1, 2], [2, 3], [3, 0]],  # v type
    't': [[0, 1, 3], [0, 1, 2], [1, 2, 3], [0, 2, 3]], #t
    'c': [[0, 1, 2, 3]], #cross
    'e': [[0], [1], [2], [3]], #end
    'n': [[]] #none
}

class Tile:
    def __init__(self, type_name: str, rotation: int = 0):
        self.type_name = type_name
        self.variations = PIPE_TYPES[type_name]
        self.rotation = rotation % len(self.variations)
        self.connections = self.variations[self.rotation]
        self.locked = False

    def rotate(self, clockwise: bool = True):
        if self.locked:
            return
        num_vars = len(self.variations)
        self.rotation = (self.rotation + (1 if clockwise else -1)) % num_vars
        self.connections = self.variations[self.rotation]

    def get_connections(self) -> List[int]:
        return self.connections

class PipesGame:
    def __init__(self, level_file: str = "level0.txt"):
        self.grid = []
        self.water_source = (0, 0)
        self.level_file = level_file
        self.grid_size = 4
        self.cell_size = 100
        self.load_level()
        self.screen_size = self.grid_size * self.cell_size

        pygame.init()
        self.screen = pygame.display.set_mode((self.screen_size, self.screen_size))
        pygame.display.set_caption("Pipes Puzzle")
        self.clock = pygame.time.Clock()
        self.running = True
        self.connected_tiles = set()
        self.update_connected_tiles()

    def load_level(self):
        # Hardcoded level data for Pyodide or fallback
        level_data = """[GRID]
grid_size=4
cell_size=50
[TILES]
e2 e0 e0 v2
v0 t1 v3 l0
e1 e1 t3 t2
v2 l1 l0 v1
[SOURCE]
3 3"""

        # For local execution, try reading the file
        try:
            with open(f"levels/{self.level_file}", "r") as f:
                level_data = f.read()
        except FileNotFoundError:
            print(f"Level file levels/{self.level_file} not found. Using default level data.")
        except Exception as e:
            print(f"Error reading level file: {e}. Using default level data.")

        try:
            # Normalize line endings and split sections
            level_data = level_data.replace('\r\n', '\n').strip()
            sections = level_data.split('\n\n')
            if len(sections) != 3:
                raise ValueError(f"Expected 3 sections ([GRID], [TILES], [SOURCE]), found {len(sections)}")

            # Parse [GRID] section
            grid_section = sections[0].split('\n')
            if grid_section[0].strip() != '[GRID]':
                raise ValueError("Missing [GRID] header")
            self.grid_size = None
            self.cell_size = None
            for line in grid_section[1:]:
                key, value = line.split('=')
                key = key.strip()
                value = value.strip()
                if key == 'grid_size':
                    self.grid_size = int(value)
                elif key == 'cell_size':
                    self.cell_size = int(value)
            if self.grid_size is None or self.cell_size is None:
                raise ValueError("grid_size or cell_size missing in [GRID] section")

            # Parse [TILES] section
            tiles_section = sections[1].split('\n')
            if tiles_section[0].strip() != '[TILES]':
                raise ValueError("Missing [TILES] header")
            tiles_section = tiles_section[1:]  # Skip [TILES]
            if len(tiles_section) != self.grid_size:
                raise ValueError(f"Expected {self.grid_size} rows in [TILES], found {len(tiles_section)}")
            for row, line in enumerate(tiles_section):
                tiles = line.split()
                if len(tiles) != self.grid_size:
                    raise ValueError(f"Row {row} in [TILES] has {len(tiles)} tiles, expected {self.grid_size}")
                grid_row = []
                for tile_str in tiles:
                    type_name = tile_str[0] if tile_str != 'n' else 'n'
                    rotation = int(tile_str[1]) if tile_str != 'n' else 0
                    if type_name not in PIPE_TYPES:
                        raise ValueError(f"Invalid tile type: {type_name}")
                    grid_row.append(Tile(type_name, rotation))
                self.grid.append(grid_row)

            # Parse [SOURCE] section
            source_section = sections[2].split('\n')
            if source_section[0].strip() != '[SOURCE]':
                raise ValueError("Missing [SOURCE] header")
            row, col = map(int, source_section[1].split())
            if not (0 <= row < self.grid_size and 0 <= col < self.grid_size):
                raise ValueError(f"Source position ({row}, {col}) out of grid bounds")
            self.water_source = (row, col)

        except Exception as e:
            print(f"Error parsing level data: {e}")
            sys.exit(1)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                x, y = pygame.mouse.get_pos()
                col = x // self.cell_size
                row = y // self.cell_size
                if 0 <= row < self.grid_size and 0 <= col < self.grid_size:
                    tile = self.grid[row][col]
                    if event.button == 1:  # Left click
                        mods = pygame.key.get_mods()
                        clockwise = not (mods & pygame.KMOD_CTRL)
                        tile.rotate(clockwise)
                    elif event.button == 3:  # Right click
                        tile.locked = not tile.locked
                self.update_connected_tiles()
                self.check_win()

    def draw_grid(self):
        self.screen.fill(BACKGROUND_COLOR)
        for i in range(self.grid_size + 1):
            pygame.draw.line(self.screen, GRID_COLOR, (0, i * self.cell_size), (self.screen_size, i * self.cell_size), 2)
            pygame.draw.line(self.screen, GRID_COLOR, (i * self.cell_size, 0), (i * self.cell_size, self.screen_size), 2)

    def draw_tile(self, row: int, col: int):
        tile = self.grid[row][col]
        center_x = col * self.cell_size + self.cell_size // 2
        center_y = row * self.cell_size + self.cell_size // 2
        half = self.cell_size // 2
        # Color logic: water source is always blue, connected tiles blue, others gray
        color = LOCKED_COLOR if tile.locked else (
            CONNECTED_COLOR if (row, col) == self.water_source or (row, col) in self.connected_tiles
            else UNCONNECTED_COLOR
        )

        dirs = {
            0: (center_x, center_y - half),  # North
            1: (center_x + half, center_y),  # East
            2: (center_x, center_y + half),  # South
            3: (center_x - half, center_y)   # West
        }

        # Draw pipe segments
        for d in tile.get_connections():
            end_pos = dirs[d]
            pygame.draw.line(self.screen, color, (center_x, center_y), end_pos, PIPE_THICKNESS)

        if tile.type_name == 'e':
            pygame.draw.circle(self.screen, color, (center_x, center_y), CENTER_CIRCLE_RADIUS)

        # Draw red circle for water source
        if (row, col) == self.water_source:
            pygame.draw.circle(self.screen, SOURCE_CIRCLE_COLOR, (center_x, center_y), CENTER_CIRCLE_RADIUS)

    def draw(self):
        self.draw_grid()
        for row in range(self.grid_size):
            for col in range(self.grid_size):
                self.draw_tile(row, col)
        pygame.display.flip()

    def get_neighbors(self, row: int, col: int) -> List[Tuple[int, int, int, int]]:
        neighbors = []
        deltas = [(-1, 0, 0, 2), (0, 1, 1, 3), (1, 0, 2, 0), (0, -1, 3, 1)]  # N, E, S, W
        for dr, dc, my_dir, their_dir in deltas:
            nr, nc = row + dr, col + dc
            if 0 <= nr < self.grid_size and 0 <= nc < self.grid_size:
                if my_dir in self.grid[row][col].get_connections() and their_dir in self.grid[nr][nc].get_connections():
                    neighbors.append((nr, nc, my_dir, their_dir))
        return neighbors

    def update_connected_tiles(self):
        # Flood-fill from water source to find connected tiles
        self.connected_tiles = set()
        from collections import deque
        stack = deque([self.water_source])
        visited = set()

        while stack:
            r, c = stack.pop()
            if (r, c) in visited:
                continue
            visited.add((r, c))
            if self.grid[r][c].get_connections():  # Skip empty tiles
                self.connected_tiles.add((r, c))
            for nr, nc, _, _ in self.get_neighbors(r, c):
                if (nr, nc) not in visited:
                    stack.append((nr, nc))

    def check_connected_and_acyclic(self) -> bool:
        parent = {}
        rank = {}
        edges = 0

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px == py:
                return False  # Cycle
            if rank[px] > rank[py]:
                parent[py] = px
            elif rank[px] < rank[py]:
                parent[px] = py
            else:
                parent[py] = px
                rank[px] += 1
            return True

        num_tiles = 0
        for r in range(self.grid_size):
            for c in range(self.grid_size):
                if self.grid[r][c].get_connections():
                    key = (r, c)
                    parent[key] = key
                    rank[key] = 0
                    num_tiles += 1

        if num_tiles == 0:
            return True
        for r in range(self.grid_size):
            for c in range(self.grid_size):
                if (r, c) in parent:
                    for nr, nc, _, _ in self.get_neighbors(r, c):
                        if (nr, nc) in parent:
                            if (r, c) < (nr, nc):  # Only count each edge once
                                edges += 1
                            if not union((r, c), (nr, nc)):
                                return False

        root = find(self.water_source)
        connected = all(find(k) == root for k in parent)
        return connected

    def check_win(self):
        if self.check_connected_and_acyclic():
            print("You win! All pipes connected without loops.")

    def run(self):
        while self.running:
            self.handle_events()
            self.draw()
            self.clock.tick(60)
        pygame.quit()

# Example usage
if __name__ == "__main__":
    level_file = sys.argv[1] if len(sys.argv) > 1 else "level0.txt"
    try:
        game = PipesGame(level_file)
        game.run()
    except Exception as e:
        print(f"Error starting game with level file '{level_file}': {e}")
        sys.exit(1)
    