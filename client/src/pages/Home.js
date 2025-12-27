import Header from "../components/Header";
import Searchbar from "../components/Searchbar";
import Loader from "../components/Loader";
import TraitsGrid from "../components/TraitsGrid";
import InsightsDisplay from "../components/InsightsDisplay";
import AnalysisHeader from "../components/AnalysisHeader";
import { useState, useContext } from "react";
import { UserContext } from "../store/store";

export default function Home() {
  const [loaderVisible, setLoaderVisible] = useState(false);
  const [error, setError] = useState("");
  const [url, setUrl] = useState("");
  const { token, user } = useContext(UserContext);
  const [analysis, setAnalysis] = useState(null);

  async function req_search() {
    if (!url) {
      setError("Please check the input fields");
      return;
    }

    try {
      setError("");
      setLoaderVisible(true);
      const timeoutMs = 60000;
      if (url.endsWith(".com")) {
        setError("Please provide a twitter url with a username.");
        return;
      }
      const response = await Promise.race([
        fetch(
          `http://127.0.0.1:5000/api/analyze_profile?url=${encodeURIComponent(
            url
          )}&count=5&email=${encodeURIComponent(user.email)}`,
          {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
          }
        ),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error("Request timed out")), timeoutMs)
        ),
      ]);

      if (response) {
        const dataJson = await response.json();
        console.log("API Response:", dataJson);

        if (response.ok) {
          const transformedData = {
            ANALYSIS_DATE: new Date().toISOString(),
            TWEETS_COUNT: dataJson.tweets_analyzed,
            AVERAGE_OPENNESS: dataJson.average_scores.openness,
            AVERAGE_CONSCIENTIOUSNESS:
              dataJson.average_scores.conscientiousness,
            AVERAGE_EXTRAVERSION: dataJson.average_scores.extraversion,
            AVERAGE_AGREEABLENESS: dataJson.average_scores.agreeableness,
            AVERAGE_NEUROTICISM: dataJson.average_scores.neuroticism,
            insights: Object.entries(dataJson.summary).flatMap(
              ([type, texts]) =>
                texts.map((text) => ({
                  INSIGHT_TYPE: type,
                  INSIGHT_TEXT: text,
                }))
            ),
          };

          console.log("Transformed Data:", transformedData);
          setAnalysis(transformedData);
        } else {
          setError(dataJson.error || dataJson.message || "Request failed");
        }
      } else {
        setError("Request timed out. Please try again later.");
      }
    } catch (error) {
      console.error("API Error:", error);
      setError("An error occurred. Please try again later.");
    } finally {
      setLoaderVisible(false);
    }
    console.log(error);
  }

  return (
    <>
      <Header type={false} />
      {loaderVisible && <Loader text={true} />}

      <span
        className="regular-text"
        style={{ textAlign: "center", marginTop: "7rem" }}
      >
        Enter a Twitter profile link to{" "}
        <span className="dynamic-word">analyze</span> the personality behind the
        tweets.
      </span>
      {!loaderVisible && error && (
        <span className={"error-text"} style={{ marginTop: "20px" }}>
          {error}
        </span>
      )}
      <Searchbar
        onChange={setUrl}
        onClick={req_search}
        disabled={loaderVisible}
      />

      {analysis && (
        <div className="analysis-result">
          <AnalysisHeader analysis={analysis} />
          <TraitsGrid traits={analysis} />
          <InsightsDisplay insights={analysis.insights} />
        </div>
      )}
    </>
  );
}
