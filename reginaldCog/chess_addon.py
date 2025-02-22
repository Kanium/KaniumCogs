import chess
import chess.svg
import io
from cairosvg import svg2png
import discord

class ChessHandler:
    def __init__(self):
        self.active_games = {}  # {user_id: FEN string}

    def set_board(self, user_id: str, fen: str):
        """Sets a board to a given FEN string for a user."""
        try:
            board = chess.Board(fen)  # Validate FEN
            self.active_games[user_id] = fen
            return f"Board state updated successfully:\n```{fen}```"
        except ValueError:
            return "⚠️ Invalid FEN format. Please provide a valid board state."

    def reset_board(self, user_id: str):
        """Resets a user's board to the standard starting position."""
        self.active_games[user_id] = chess.STARTING_FEN
        return "The board has been reset to the standard starting position."

    def get_board(self, user_id: str):
        """Returns a chess.Board() instance based on stored FEN."""
        fen = self.active_games.get(user_id, chess.STARTING_FEN)
        return chess.Board(fen)

    def get_fen(self, user_id: str):
        """Returns the current FEN of the user's board."""
        return self.active_games.get(user_id, chess.STARTING_FEN)

    def make_move(self, user_id: str, move: str):
        """Attempts to execute a move and checks if the game is over."""
        board = self.get_board(user_id)

        try:
            board.push_san(move)  # Execute move in standard algebraic notation
            self.active_games[user_id] = board.fen()  # Store FEN string instead of raw board object

            if board.is_checkmate():
                self.active_games.pop(user_id)
                return f"Move executed: `{move}`. **Checkmate!** 🎉"
            elif board.is_stalemate():
                self.active_games.pop(user_id)
                return f"Move executed: `{move}`. **Stalemate!** 🤝"
            elif board.is_insufficient_material():
                self.active_games.pop(user_id)
                return f"Move executed: `{move}`. **Draw due to insufficient material.**"
            elif board.can_claim_threefold_repetition():
                self.active_games.pop(user_id)
                return f"Move executed: `{move}`. **Draw by threefold repetition.**"
            elif board.can_claim_fifty_moves():
                self.active_games.pop(user_id)
                return f"Move executed: `{move}`. **Draw by 50-move rule.**"

            return f"Move executed: `{move}`.\nCurrent FEN:\n```{board.fen()}```"
        except ValueError:
            return "⚠️ Invalid move. Please enter a legal chess move."

    def resign(self, user_id: str):
        """Handles player resignation."""
        if user_id in self.active_games:
            del self.active_games[user_id]
            return "**You have resigned. Well played!** 🏳️"
        return "No active game to resign from."

    def get_board_state_text(self, user_id: str):
        """Returns the current FEN as a message."""
        fen = self.active_games.get(user_id, chess.STARTING_FEN)
        return f"Current board state (FEN):\n```{fen}```"

    def get_board_state_image(self, user_id: str):
        """Generates a chessboard image from the current FEN and returns it as a file."""
        fen = self.active_games.get(user_id, chess.STARTING_FEN)
        board = chess.Board(fen)

        try:
            # Generate SVG representation of the board
            svg_data = chess.svg.board(board)

            # Convert SVG to PNG using cairosvg
            png_data = svg2png(bytestring=svg_data)

            # Store PNG in memory
            image_file = io.BytesIO(png_data)
            image_file.seek(0)  # Ensure file pointer is reset before returning

            return discord.File(image_file, filename="chessboard.png")

        except Exception as e:
            return f"⚠️ Error generating board image: {str(e)}"
