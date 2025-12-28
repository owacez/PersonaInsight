export default function Button({ text, onClick, disabled }) {
  return (
    <button
      className={`button ${disabled ? "disabled-element" : ""}`}
      onClick={onClick}
      disabled={disabled}
    >
      {text}
    </button>
  );
}
