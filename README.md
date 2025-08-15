# PersonaInsight

**PersonaInsight** PersonaInsight is a web-based personality analysis application that uses the OCEAN (Big Five) personality model to assess traits from Twitter data. Built with React (frontend) and Flask (backend), it allows users to link their Twitter profile, scrape recent tweets, and receive a detailed personality breakdown displayed on an interactive dashboard.

## 🌐 Project Structure

```
PersonaInsight/
├── client/   # React frontend for UI interaction
└── server/   # Python backend for personality analysis and API handling
```

---

## 📦 Prerequisites

Before running the application, make sure you have the following installed:

- Node.js & npm
- Python 3.12
- pip (Python package installer)
- Git
- PyCharm (optional, for running backend server)
- Microsoft SQL Server

---

## 🗂 Download MyPersonality Dataset

1. Go to Kaggle
2. Download the mypersonality_final dataset and extract the contents.
3. Place the dataset in an appropriate directory referenced by your backend.

---

## 🛠 Installation & Setup

### 1. Clone the Repository
- bash
- git clone https://github.com/devowaisys/Persona.git
- cd PersonaInsight

### 2. Backend Setup
- cd server
- pip install -r requirements.txt
- python app.py (You can run the backend either using Python or via PyCharm)

### 2. Client Setup
- cd client
- npm install
- npm start

### 3. Database Setup
- Open Microsoft SQL Server Management Studio.
- Create a new database named PersonaInsight.
- Click on the PersonaInsight database and select New Query.
- Paste the following SQL script and click Execute to create the necessary tables and relationships.

```
CREATE TABLE USERS (
    ID int IDENTITY(1,1) NOT NULL,
    FULLNAME nchar(30) NOT NULL,
    EMAIL nchar(50),
    PASSWORD nchar(30),
    PRIMARY KEY (EMAIL)
);

CREATE TABLE ANALYSIS (
    ANALYSIS_ID INT PRIMARY KEY IDENTITY(1,1),
    EMAIL NCHAR(50) REFERENCES users(EMAIL),
	  USERNAME NCHAR(30) NOT NULL,
    ANALYSIS_DATE DATETIME DEFAULT GETDATE(),
    TWEETS_COUNT INT NOT NULL,
    AVERAGE_AGREEABLENESS DECIMAL(5,4),
    AVERAGE_CONSCIENTIOUSNESS DECIMAL(5,4),
    AVERAGE_EXTRAVERSION DECIMAL(5,4),
    AVERAGE_NEUROTICISM DECIMAL(5,4),
    AVERAGE_OPENNESS DECIMAL(5,4)
);

CREATE TABLE INSIGHTS (
    INSIGHT_ID INT PRIMARY KEY IDENTITY(1,1),
    ANALYSIS_ID INT REFERENCES ANALYSIS(ANALYSIS_ID),
    INSIGHT_TYPE VARCHAR(255) NOT NULL,
    INSIGHT_TEXT NVARCHAR(255) NOT NULL
);

```
