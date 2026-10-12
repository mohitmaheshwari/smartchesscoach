/**
 * chessMoveHelper.js
 *
 * Beginner-friendly helpers for describing chess moves in plain English.
 * Translates SAN notations like "Rh8", "fxe5", "Nf3", "O-O" into
 * easy-to-understand labels with piece icons and player context.
 */

export function describeChessMove(san, isWhiteMove = true, userColor = "white") {
  if (!san || san === "Start" || san === "start") {
    return {
      san: "Start",
      pieceIcon: "♟",
      pieceName: "Game",
      action: "Game Start",
      plain: "Game Start",
      who: "Game",
      full: "Game Start",
      short: "Start",
      dest: "",
    };
  }

  const isUser = (userColor === "white" && isWhiteMove) || (userColor === "black" && !isWhiteMove);
  const who = isUser ? "You" : "Coach";

  const isCheckmate = san.includes("#");
  const isCheck = san.includes("+") && !isCheckmate;
  const isCapture = san.includes("x");

  // Castling
  if (san === "O-O" || san === "0-0") {
    const icon = isWhiteMove ? "♔" : "♚";
    return {
      san,
      pieceIcon: icon,
      pieceName: "King",
      action: "Short Castle (Kingside)",
      plain: "King castles kingside (O-O)",
      who,
      isUser,
      full: `${who} castled kingside (O-O)`,
      short: `${who}: ${icon} O-O (Castle)`,
      dest: isWhiteMove ? "g1" : "g8",
    };
  }

  if (san === "O-O-O" || san === "0-0-0") {
    const icon = isWhiteMove ? "♔" : "♚";
    return {
      san,
      pieceIcon: icon,
      pieceName: "King",
      action: "Long Castle (Queenside)",
      plain: "King castles queenside (O-O-O)",
      who,
      isUser,
      full: `${who} castled queenside (O-O-O)`,
      short: `${who}: ${icon} O-O-O (Castle)`,
      dest: isWhiteMove ? "c1" : "c8",
    };
  }

  // Strip check and mate symbols for clean parsing
  const clean = san.replace(/[+#]/g, "");

  let pieceIcon = isWhiteMove ? "♙" : "♟";
  let pieceName = "Pawn";
  let dest = clean.slice(-2);

  if (clean.startsWith("K")) {
    pieceIcon = isWhiteMove ? "♔" : "♚";
    pieceName = "King";
  } else if (clean.startsWith("Q")) {
    pieceIcon = isWhiteMove ? "♕" : "♛";
    pieceName = "Queen";
  } else if (clean.startsWith("R")) {
    pieceIcon = isWhiteMove ? "♖" : "♜";
    pieceName = "Rook";
  } else if (clean.startsWith("B")) {
    pieceIcon = isWhiteMove ? "♗" : "♝";
    pieceName = "Bishop";
  } else if (clean.startsWith("N")) {
    pieceIcon = isWhiteMove ? "♘" : "♞";
    pieceName = "Knight";
  }

  // Pawn promotion
  let promo = "";
  if (san.includes("=")) {
    const p = san.split("=")[1]?.[0];
    promo = p === "Q" ? " → Promotes to Queen" : p === "R" ? " → Promotes to Rook" : p === "B" ? " → Promotes to Bishop" : " → Promotes to Knight";
  }

  const verb = isCapture ? "takes on" : "to";
  const checkSuffix = isCheckmate ? " (Checkmate!)" : isCheck ? " (Check!)" : "";
  const plain = `${pieceName} ${verb} ${dest}${promo}${checkSuffix}`;
  const full = `${who} played ${pieceName} ${verb} ${dest}${promo}${checkSuffix}`;

  return {
    san,
    pieceIcon,
    pieceName,
    dest,
    isCapture,
    isCheck,
    isCheckmate,
    who,
    isUser,
    plain,
    full,
    short: `${who}: ${pieceIcon} ${san}`,
  };
}
