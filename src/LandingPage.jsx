import "./LandingPage.css";
import logo from "./assets/logo.svg";
import { useState } from "react";

function LandingPage() {
  const [email, setEmail] = useState("");

const handleSubscribe = async (e) => {
  e.preventDefault();

  if (!email.trim()) {
    alert("Adj meg egy email címet!");
    return;
  }

  try {
    const res = await fetch("https://ajanlat-app.onrender.com/subscribe", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email }),
    });

    const data = await res.json();

    if (data.error) {
      alert(data.error);
    } else {
      alert("Sikeres feliratkozás!");
      setEmail("");
    }
  } catch (err) {
    alert("Hiba történt, próbáld újra.");
  }
};

  return (
    <div className="landing">
      <div className="bg-shape shape-1"></div>
      <div className="bg-shape shape-2"></div>
      <div className="bg-shape shape-3"></div>
      <div className="bg-ring ring-1"></div>
      <div className="bg-ring ring-2"></div>
      <div className="bg-dots"></div>

      <nav className="nav">
        <div className="logo">
          <img src={logo} alt="Ajánlat App logó" />
        </div>

        <div className="menu">
          <a href="#home">Home</a>
          <a href="#features">Funkciók</a>
          <a href="#about">Miért jobb?</a>
          <a href="#subscribe">Feliratkozás</a>
          <a href="/app">Belépés</a>
        </div>
      </nav>

      <section className="hero" id="home">
        <span className="hero-badge">Modern SaaS megoldás vállalkozóknak</span>

        <h1>Profi ajánlatkészítés percek alatt</h1>

        <p>
          Hagyd az Excelt. Készíts modern, átlátható és automatikus
          ajánlatokat sablonokkal, PDF exporttal és gyors projektszerkesztéssel.
        </p>

        <div className="buttons">
          <a href="/app">
            <button className="primary">Próbáld ki</button>
          </a>

          <a href="#features">
            <button className="secondary">Tudj meg többet</button>
          </a>
        </div>
      </section>

      <section className="features" id="features">
        <div className="section-container">
          <div className="features-header centered-text">
            <span className="section-badge">Miért hasznos?</span>
            <h2>Az ajánlatadás többé nem lassú és kaotikus</h2>
            <p>
              Egyszerűbb folyamat, gyorsabb ajánlatkészítés és átláthatóbb
              munkavégzés vállalkozóknak.
            </p>
          </div>

          <div className="feature-grid">
            <div className="feature-card">
              <div className="feature-icon">01</div>
              <h3>Ne Excelben dolgozz</h3>
              <p>
                Felejtsd el a nehezen kezelhető táblázatokat és a kézi
                számolgatást.
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">02</div>
              <h3>Sablonokkal gyorsabb</h3>
              <p>
                A gyakran használt tételeket és ajánlati struktúrákat pár
                kattintással újra felhasználhatod.
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">03</div>
              <h3>PDF egy kattintással</h3>
              <p>
                Készíts letisztult, ügyfélnek küldhető ajánlatot automatikusan
                generált PDF-ben.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="comparison" id="about">
        <div className="section-container">
          <div className="comparison-left centered-text">
            <span className="section-badge">Miért jobb?</span>
            <h2>Excel helyett egy gyorsabb, átláthatóbb rendszer</h2>
            <p>
              Az ajánlatkészítés nem kell, hogy kézi másolgatásból,
              számolgatásból és széteső táblázatokból álljon. Az app célja, hogy
              gyorsabban és profibban tudj dolgozni.
            </p>

            <div className="comparison-points">
              <div className="point-item">
                <div className="point-dot"></div>
                <span>Kevesebb kézi munka és hibalehetőség</span>
              </div>

              <div className="point-item">
                <div className="point-dot"></div>
                <span>Gyors sablon alapú ajánlatkészítés</span>
              </div>

              <div className="point-item">
                <div className="point-dot"></div>
                <span>Professzionális PDF export egy kattintással</span>
              </div>

              <div className="point-item">
                <div className="point-dot"></div>
                <span>Átlátható projektek, tételek és végösszeg</span>
              </div>
            </div>
          </div>

          <div className="comparison-right">
            <div className="compare-card old-way">
              <h3>Excel / régi módszer</h3>
              <ul>
                <li>Kézi másolás</li>
                <li>Kézi számolás</li>
                <li>Széteső sablonok</li>
                <li>Lassú PDF készítés</li>
              </ul>
            </div>

            <div className="compare-card new-way">
              <h3>Ajánlat App</h3>
              <ul>
                <li>Gyors sablonkezelés</li>
                <li>Automatikus végösszeg</li>
                <li>Projekt alapú működés</li>
                <li>PDF generálás azonnal</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className="cta-section">
        <div className="section-container">
          <div className="cta-card">
            <span className="section-badge">Indulásra kész</span>
            <h2>Próbáld ki az Ajánlat Appot</h2>
            <p>
              Készíts gyorsabban ajánlatot, kezeld sablonokkal a gyakori
              tételeket, és generálj profi PDF-et egy kattintással.
            </p>

            <div className="cta-buttons">
              <a href="/app">
                <button className="primary">Belépés az appba</button>
              </a>
            </div>
          </div>
        </div>
      </section>

      <section className="subscribe-section" id="subscribe">
        <div className="section-container">
          <div className="subscribe-card">
            <span className="section-badge">Maradj kapcsolatban</span>
            <h2>Kérj értesítést az indulásról</h2>
            <p>
              Add meg az email címed, és szólunk, amikor indul a szolgáltatás,
              új funkció érkezik, vagy megnyílik a korai hozzáférés.
            </p>

            <form className="subscribe-form" onSubmit={handleSubscribe}>
              <input
                type="email"
                placeholder="Email címed"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <button type="submit" className="primary">
                Feliratkozom
              </button>
            </form>

            <p className="subscribe-note">
              Nincs spam. Csak fontos frissítések és indulási értesítés.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

export default LandingPage;