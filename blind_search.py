import sys
import pygame
import heapq
from collections import deque

# ---------------- PIPE DEFINITIONS ---------------- #
PIPE_TYPES = {
    'l': [[1, 3], [0, 2]],  # straight line
    'v': [[0, 1], [1, 2], [2, 3], [3, 0]],  # elbow
    't': [[0, 1, 3], [0, 1, 2], [1, 2, 3], [0, 2, 3]],  # T
    'c': [[0, 1, 2, 3]],  # cross
    'e': [[0], [1], [2], [3]],  # end
    'n': [[]]  # none
}

# directions: 0=up,1=right,2=down,3=left
DIRS = [(-1, 0), (0, 1), (1, 0), (0, -1)]


# ---------------- BASIC CLASSES ---------------- #
class Action:
    def __init__(self, pos, rotation):
        self.pos = pos  # (r,c)
        self.rotation = rotation  # 0..3

    def __repr__(self):
        return f"Rotate {self.pos} -> {self.rotation}"


class Tile:
    def __init__(self, type_char, rotation=0):
        self.type = type_char
        self.rotation = rotation

    def rotate(self, rot):
        return Tile(self.type, rot)

    def get_connections(self):
        if self.type not in PIPE_TYPES:
            return []
        variations = PIPE_TYPES[self.type]
        rot = self.rotation % len(variations)
        return [DIRS[d] for d in variations[rot]]

    def __repr__(self):
        return f"{self.type}{self.rotation}"


class GameState:
    def __init__(self, grid_size, tiles, source):
        self.grid_size = grid_size
        self.tiles = tiles  # {(r,c): Tile}
        self.source = source  # (r,c)

    def hash(self):
        return tuple((pos, t.type, t.rotation) for pos, t in sorted(self.tiles.items()))

    def __eq__(self, other):
        return self.hash() == other.hash()

    def is_goal(self):
        # BFS from source following connections
        visited = set()
        frontier = [self.source]
        while frontier:
            r, c = frontier.pop()
            if (r, c) in visited:
                continue
            visited.add((r, c))
            if (r, c) not in self.tiles:
                continue
            tile = self.tiles[(r, c)]
            for dr, dc in tile.get_connections():
                nr, nc = r + dr, c + dc
                if (nr, nc) in self.tiles:
                    neighbor = self.tiles[(nr, nc)]
                    if (-dr, -dc) in [DIRS[d] for d in PIPE_TYPES[neighbor.type][neighbor.rotation % len(PIPE_TYPES[neighbor.type])]]:
                        frontier.append((nr, nc))
        return len(visited) == len(self.tiles)

    def get_possible_actions(self):
        actions = []
        for pos, tile in self.tiles.items():
            variations = PIPE_TYPES[tile.type]
            for rot in range(len(variations)):
                if rot != tile.rotation:
                    # optimization: avoid end-to-end facing
                    if tile.type == "e":
                        # skip if would face another end
                        for (dr, dc) in [DIRS[d] for d in PIPE_TYPES[tile.type][rot]]:
                            nr, nc = pos[0] + dr, pos[1] + dc
                            if (nr, nc) in self.tiles and self.tiles[(nr, nc)].type == "e":
                                break
                        else:
                            actions.append(Action(pos, rot))
                    else:
                        actions.append(Action(pos, rot))
        return actions

    def apply_action(self, action):
        new_tiles = dict(self.tiles)
        new_tiles[action.pos] = new_tiles[action.pos].rotate(action.rotation)
        return GameState(self.grid_size, new_tiles, self.source)

    def get_connected_tiles(self):
        visited = set()
        frontier = [self.source]
        while frontier:
            r, c = frontier.pop()
            if (r, c) in visited or (r, c) not in self.tiles:
                continue
            visited.add((r, c))
            tile = self.tiles[(r, c)]
            for dr, dc in tile.get_connections():
                nr, nc = r + dr, c + dc
                if (nr, nc) in self.tiles:
                    neighbor = self.tiles[(nr, nc)]
                    if (-dr, -dc) in [DIRS[d] for d in PIPE_TYPES[neighbor.type][neighbor.rotation % len(PIPE_TYPES[neighbor.type])]]:
                        frontier.append((nr, nc))
        return visited


# ---------------- A* SOLVER ---------------- #
class AISolver:
    def __init__(self, initial_state):
        self.initial_state = initial_state

    def heuristic(self, state: GameState) -> int:
        connected = len(state.get_connected_tiles())
        dangling = 0
        for (r, c), tile in state.tiles.items():
            for (dr, dc) in tile.get_connections():
                nr, nc = r + dr, c + dc
                if (nr, nc) not in state.tiles:
                    dangling += 1
                else:
                    neighbor = state.tiles[(nr, nc)]
                    if (-dr, -dc) not in neighbor.get_connections():
                        dangling += 1
        return -(connected * 10) + dangling

    def solve(self):
        frontier = []
        heapq.heappush(frontier, (0, 0, self.initial_state, []))
        explored = {}
        counter = 0

        while frontier:
            f, _, state, path = heapq.heappop(frontier)
            if state.is_goal():
                print("iterations: ", counter)
                return path
            if state.hash() in explored and explored[state.hash()] <= f:
                continue
            explored[state.hash()] = f

            g = len(path)
            for action in state.get_possible_actions():
                new_state = state.apply_action(action)
                h = self.heuristic(new_state)
                new_f = g + 1 + h
                counter += 1
                heapq.heappush(frontier, (new_f, counter, new_state, path + [action]))
        
        
        return None


# ---------------- PARSER ---------------- #
def parse_level(path):
    with open(path, "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    grid_size = 0
    cell_size = 100
    tiles = {}
    source = (0, 0)

    mode = None
    row = 0
    for line in lines:
        if line.startswith("["):
            if line == "[GRID]": mode = "grid"
            elif line == "[TILES]": mode = "tiles"; row = 0
            elif line == "[SOURCE]": mode = "source"
            continue

        if mode == "grid":
            if line.startswith("grid_size="):
                grid_size = int(line.split("=")[1])
            elif line.startswith("cell_size="):
                cell_size = int(line.split("=")[1])
        elif mode == "tiles":
            parts = line.split()
            for col, token in enumerate(parts):
                t, rot = token[0], int(token[1])
                tiles[(row, col)] = Tile(t, rot)
            row += 1
        elif mode == "source":
            r, c = map(int, line.split())
            source = (r, c)

    return grid_size, cell_size, tiles, source

def draw(screen, state, grid_size, cell_size):
    # Colors
    BACKGROUND_COLOR = (30, 30, 30)
    GRID_COLOR = (80, 80, 80)
    CONNECTED_COLOR = (0, 0, 255)
    UNCONNECTED_COLOR = (200, 200, 200)
    SOURCE_COLOR = (255, 0, 0)
    PIPE_THICKNESS = 10
    CENTER_CIRCLE_RADIUS = PIPE_THICKNESS

    # Fill background
    screen.fill(BACKGROUND_COLOR)

    # Draw grid lines
    for i in range(grid_size + 1):
        pygame.draw.line(screen, GRID_COLOR, (0, i * cell_size), (grid_size * cell_size, i * cell_size), 2)
        pygame.draw.line(screen, GRID_COLOR, (i * cell_size, 0), (i * cell_size, grid_size * cell_size), 2)

    # Get connected tiles for coloring
    connected = state.get_connected_tiles()

    # Draw tiles
    for (r, c), tile in state.tiles.items():
        center_x = c * cell_size + cell_size // 2
        center_y = r * cell_size + cell_size // 2
        half = cell_size // 2

        # Color logic
        color = CONNECTED_COLOR if (r, c) == state.source or (r, c) in connected else UNCONNECTED_COLOR

        # Directions: 0-N, 1-E, 2-S, 3-W
        dirs = {
            0: (center_x, center_y - half),
            1: (center_x + half, center_y),
            2: (center_x, center_y + half),
            3: (center_x - half, center_y)
        }

        # Draw pipe segments
        for d in PIPE_TYPES[tile.type][tile.rotation % len(PIPE_TYPES[tile.type])]:
            end_pos = dirs[d]
            pygame.draw.line(screen, color, (center_x, center_y), end_pos, PIPE_THICKNESS)

        # Draw center circle for 'e' (end) tiles
        if tile.type == 'e':
            pygame.draw.circle(screen, color, (center_x, center_y), CENTER_CIRCLE_RADIUS)

        # Draw red circle for source
        if (r, c) == state.source:
            pygame.draw.circle(screen, SOURCE_COLOR, (center_x, center_y), CENTER_CIRCLE_RADIUS)

        # Draw tile type+rotation text
        # font = pygame.font.SysFont(None, 24)
        # text = font.render(str(tile), True, (220, 220, 220))
        # screen.blit(text, (c * cell_size + 10, r * cell_size + 10))

# ---------------- PYGAME VIEWER ---------------- #
def run_viewer(state, solution, cell_size):
    pygame.init()
    screen = pygame.display.set_mode((state.grid_size * cell_size, state.grid_size * cell_size))
    clock = pygame.time.Clock()

    step = 0
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_RIGHT:
                if step < len(solution):
                    state = state.apply_action(solution[step])
                    step += 1

        draw(screen, state, state.grid_size, cell_size)

        # pygame.display.flip()
        # clock.tick(30)
    # pygame.quit()


        # screen.fill((30, 30, 30))
        # for (r, c), tile in state.tiles.items():
        #     rect = pygame.Rect(c * cell_size, r * cell_size, cell_size, cell_size)
        #     pygame.draw.rect(screen, (80, 80, 80), rect, 1)
        #     # draw tile type+rotation text
        #     font = pygame.font.SysFont(None, 24)
        #     text = font.render(str(tile), True, (200, 200, 200))
        #     screen.blit(text, (c * cell_size + 10, r * cell_size + 10))
        pygame.display.flip()
        clock.tick(30)
    pygame.quit()


# ---------------- MAIN ---------------- #
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python blind_search.py level.txt")
        sys.exit(1)

    grid_size, cell_size, tiles, source = parse_level(sys.argv[1])
    state = GameState(grid_size, tiles, source)

    print("Solving with A*...")
    solver = AISolver(state)
    solution = solver.solve()
    if solution:
        print(f"Solution found in {len(solution)} steps")
    else:
        print("No solution found.")

    run_viewer(state, solution or [], cell_size)
