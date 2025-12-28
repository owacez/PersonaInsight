import Button from "./Button";

export default function Searchbar({
  onClick,
  onChange,
  disabled,
  setTweetCount,
  setRealtimeProcessing,
}) {
  return (
    <>
      <div
        className={"form-container-horizontal"}
        style={{ alignSelf: "center", marginTop: "10px" }}
      >
        <input
          type="search"
          className={`searchbar ${disabled ? "disabled-element" : ""}`}
          placeholder="Profile Link"
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
        />
        <input
          type="number"
          className={`searchbar ${disabled ? "disabled-element" : ""}`}
          placeholder="No. of Tweets"
          onChange={(e) => setTweetCount(e.target.value)}
          style={{ width: "20%" }}
          disabled={disabled}
        />
        <label
          for="realtimeProcessing"
          className={`regular-text ${disabled ? "disabled-element" : ""}`}
          style={{ textAlign: "center", alignContent: "center" }}
          disabled={disabled}
        >
          Realtime Processing
        </label>
        <input
          type="checkbox"
          id="realtimeProcessing"
          onChange={(e) => setRealtimeProcessing(e.target.checked)}
          disabled={disabled}
        />
      </div>

      <Button
        text={disabled ? "Searching..." : "Search"}
        onClick={onClick}
        disabled={disabled}
      />
    </>
  );
}
