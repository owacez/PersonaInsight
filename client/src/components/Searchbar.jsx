import Button from "./Button";

export default function Searchbar({ onClick, onChange, disabled }) {
  return (
    <>
      <input
        type="search"
        className="searchbar"
        placeholder="Profile Link"
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      />
      <Button
        text={disabled ? "Searching..." : "Search"}
        onClick={onClick}
        disabled={disabled}
      />
    </>
  );
}
