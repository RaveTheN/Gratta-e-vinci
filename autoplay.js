const { mouse, Point } = require("@nut-tree-fork/nut-js");
const tesseract = require("tesseract.js");
const screenshot = require("screenshot-desktop");
const { Jimp } = require("jimp");

// Configura la velocità del mouse
mouse.config.mouseSpeed = 100; // Imposta una velocità del mouse (opzionale)

// Funzione per catturare una porzione dello schermo
async function captureScreen(x, y, width, height) {
  return new Promise((resolve, reject) => {
    screenshot({ format: "png" })
      .then(async (img) => {
        const image = await Jimp.read(img);
        image.crop({ x: x, y: y, w: width, h: height });
        image.normalize();
        image.scale(2);
        image.convolute([
          [-1, -1, 0],
          [-1, 1, 1],
          [0, 1, 1],
        ]);
        await image.write("capture.png");

        resolve("capture.png");
      })
      .catch((err) => reject(err));
  });
}
// Funzione per leggere il testo dall'immagine
async function readTextFromImage(imagePath) {
  const result = await tesseract.recognize(imagePath, "eng"); // Usa l'inglese come lingua
  return result.data.text.trim();
}

// Funzione che restituisce una Promise che si risolve dopo un certo tempo
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Funzione per cliccare in base al testo letto
async function performClickBasedOnText() {
  const scopri = new Point(1581, 849);
  const aumenta = new Point(1613, 780);
  const diminuisci = new Point(1565, 780);

  const probabilita = 5.49;
  let perseConsecutive = -1;

  let perse = -1;
  let vinte = 0;

  let aumenti = 0;
  try {
    // Specifica la porzione di schermo da analizzare
    const x = 1400,
      y = 1500,
      width = 150,
      height = 30; // Adatta questi valori alla tua necessità

    setTimeout(() => {
      //wait half second
    }, 500);

    //Leggi il testo dalla porzione di schermo
    const text = await readTextFromImage(
      await captureScreen(x, y, width, height)
    );
    console.log("Testo letto:", text);

    let baseValue = parseFloat(text.replace(",", ".")).toFixed(2);

    //ciclo di gioco

    for (let i = 1; i > 0; ) {
      let newScreen = await readTextFromImage(
        await captureScreen(x, y, width, height)
      );
      console.log("Valore base:", baseValue);
      let newValue = parseFloat(newScreen.replace(",", ".")).toFixed(2);
      console.log("Nuovo valore:", newValue);
      console.log("Perse:", perse);
      console.log("Perse consecutive:", perseConsecutive);
      console.log("Vinte:", vinte);
      console.log("Aumenti:", aumenti);
      console.log("differenza:", parseFloat(newValue - baseValue).toFixed(2));

      await sleep(1000);
      if (
        newValue === 0 ||
        newValue === 0.0 ||
        newValue === NaN ||
        newValue === undefined ||
        newValue === null ||
        newValue === "" ||
        newValue === " " ||
        newValue === "NaN" ||
        newValue === "0" ||
        newValue === "0.00" ||
        newValue === "undefined" ||
        newValue === "null" ||
        newValue === " "
      ) {
        break;
      } else if (newValue < baseValue) {
        perseConsecutive++;
        perse++;
        if (perseConsecutive > probabilita) {
          aumenti++;
        }
      } else if (newValue > baseValue) {
        await sleep(2000);

        if (`${parseFloat(newValue - baseValue).toFixed(2)}` === "0.10") {
          console.log("falsa vincita");
        } else {
          for (let i = -1; i <= aumenti; i++) {
            await sleep(200);
            await mouse.move(diminuisci); // Sposta il mouse
            await mouse.leftClick(); // Clic sinistro
            vinte++;
          }
          perseConsecutive = 0;
          aumenti = 0;
        }
      } else if (newValue === baseValue) {
        if (perseConsecutive > probabilita) {
          await sleep(2000);
          await mouse.move(aumenta); // Sposta il mouse
          await mouse.leftClick(); // Clic sinistro
        }

        await mouse.move(scopri); // Sposta il mouse
        await mouse.leftClick(); // Clic sinistro
      }
      baseValue = newValue;
    }

    // Rimuovi lo screenshot temporaneo
    // fs.unlinkSync(imagePath);
  } catch (err) {
    console.error("Errore:", err);
  }
}

// Esegui il programma
performClickBasedOnText();
