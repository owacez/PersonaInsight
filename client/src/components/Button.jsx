export default function Button({ text, onClick, disabled }) {
  return (
    <button
      className={`button ${disabled ? "button-disabled" : ""}`}
      onClick={onClick}
      disabled={disabled}
    >
      {text}
    </button>
  );
}
