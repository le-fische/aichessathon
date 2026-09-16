import os
import sys

import chess

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import agent


def test_regression_round6():
    print("Testing round 6 (threefold repetition avoidance)")
    # FEN +3 with a passed pawn on a6, shuffling sequence Rh4 Bf5 Rf4 Bh3.
    fen = "6k1/8/P7/5b2/7R/8/8/7K w - - 0 1"
    
    board = chess.Board(fen)
    
    agent.game_board = None
    agent.position_counts.clear()

    # Give it a sequence where Black stubbornly shuffles the bishop
    for _i in range(20):
        move_uci = agent.get_move(board.fen(), 10_000)
        move = chess.Move.from_uci(move_uci)
        board.push(move)
        
        pos_key = board._transposition_key()
        assert agent.position_counts[pos_key] < 3, (
            f"Agent walked into a 3-fold repetition! Move: {move_uci}"
        )
        
        if board.is_checkmate():
            break
            
        legal_moves = list(board.legal_moves)
        chosen = None
        for m in legal_moves:
            board.push(m)
            pos2 = board._transposition_key()
            # Black tries to repeat if possible
            if pos2 in agent.position_counts and agent.position_counts[pos2] == 1:
                chosen = m
                board.pop()
                break
            board.pop()
            
        if chosen is None:
            chosen = legal_moves[0]
            
        board.push(chosen)
        pos_key = board._transposition_key()
        # The agent.position_counts is only incremented when agent.get_move is called.
        # But we can assert the board itself hasn't reached threefold repetition.
        assert not board.is_repetition(3), "Opponent caused a 3-fold repetition!"
        
    print("Round 6 test passed. No threefold repetition reached.")


def test_regression_round17():
    print("Testing round 17 (K+R vs K checkmate conversion without repetition)")
    fen = "4R3/8/8/3k1K2/8/8/8/8 w - - 15 83"
    
    agent.game_board = None
    agent.position_counts.clear()
    
    board = chess.Board(fen)
    moves_played = 0
    while not board.is_game_over() and moves_played < 50:
        if board.turn == chess.WHITE:
            move_uci = agent.get_move(board.fen(), 10_000)
            move = chess.Move.from_uci(move_uci)
        else:
            move = next(iter(board.legal_moves))
            
        board.push(move)
        
        if board.turn == chess.WHITE:
            pos_key = board._transposition_key()
            assert agent.position_counts[pos_key] < 3, "Agent allowed a 3-fold repetition!"
            
        moves_played += 1
        
    assert board.is_checkmate(), "Failed to mate K+R vs K within 50 plies!"
    assert not board.is_repetition(3), "Threefold repetition occurred!"
    print("Round 17 test passed. Checkmate achieved.")

if __name__ == "__main__":
    test_regression_round6()
    test_regression_round17()
