const { mouse, Point } = require("@nut-tree-fork/nut-js");
const tesseract = require("tesseract.js");
const screenshot = require("screenshot-desktop");
const { Jimp } = require("jimp");

// Configura la velocità del mouse
mouse.config.mouseSpeed = 100; // Imposta una velocità del mouse (opzionale)

// Funzione per generare un numero casuale da 1 a 25
function getRandomNumber() {
  return Math.floor(Math.random() * 25) + 1; // Genera un numero casuale tra 1 e 25
}

//Posizioni dei punti di click
let t1 = new Point(1581, 849);
let t2 = new Point(1613, 780);
let t3 = new Point(1565, 780);
let t4 = new Point(1581, 780);
let t5 = new Point(1613, 849);
let t6 = new Point(1565, 849);
let t7 = new Point(1581, 780);
let t8 = new Point(1613, 780);
let t9 = new Point(1565, 780);
let t10 = new Point(1581, 849);
let t11 = new Point(1613, 780);
let t12 = new Point(1565, 780);
let t13 = new Point(1581, 780);
let t14 = new Point(1613, 849);
let t15 = new Point(1565, 849);
let t16 = new Point(1581, 780);
let t17 = new Point(1613, 780);
let t18 = new Point(1565, 780);
let t19 = new Point(1581, 849);
let t20 = new Point(1613, 780);
let t21 = new Point(1565, 780);
let t22 = new Point(1581, 780);
let t23 = new Point(1613, 849);
let t24 = new Point(1565, 849);
let t25 = new Point(1581, 780);

let play_collect = new Point(1581, 849);

let raise = new Point(1613, 780);
let lower = new Point(1565, 780);

let color = { r: 0, g: 0, b: 0, a: 0 };

// Define target colors
const targetBlue = { r: 0, g: 0, b: 255 }; // Pure blue
const targetRed = { r: 255, g: 0, b: 0 }; // Pure red

const isBlue = isColorInRange_blue(color, targetBlue);
const isRed = isColorInRange_red(color, targetRed);

let cash = 0;
let bet = 0.1;

//Funzione per aumentare la puntata
async function increaseBet() {
  await mouse.move(raise);
  await mouse.click();
  bet += 0.1; // Aumenta la puntata di 0.1
}

//Funzione per diminuire la puntata
async function decreaseBet() {
  await mouse.move(lower);
  await mouse.click();
  bet -= 0.1; // Diminuisce la puntata di 0.1
}

//Funzione per giocare/riscuotere
async function playOrCollect() {
  await mouse.move(play_collect);
  await mouse.click();
}

// Funzione per dimuinire la puntata al minimo
async function decreaseBetToMinimum() {
  while (bet > 0.1) {
    await decreaseBet();
    console.log("Puntata diminuita a:", bet);
    await sleep(500); // Attendi mezzo secondo tra le diminuzioni
  }
}

// Funzione per diminuire la puntata di forza (click * 100)
async function decreaseBetForce() {
  for (let i = 0; i < 100; i++) {
    await decreaseBet();
    console.log("Puntata diminuita a:", bet);
    await sleep(10); // Attendi un breve periodo tra le diminuzioni
  }
  bet = 0.1; // Assicurati che la puntata non scenda sotto il minimo
}

// Funzione per leggere il colore in un punto dello schermo
async function readColorAtPoint(point) {
  return new Promise((resolve, reject) => {
    screenshot({ format: "png" })
      .then(async (img) => {
        const image = await Jimp.read(img);
        const color = image.getPixelColor(point.x, point.y);
        resolve(Jimp.intToRGBA(color));
      })
      .catch((err) => reject(err));
  });
}

// Funzione per capire se il colore è nel range del blu
function isColorInRange_blue(color, targetColor, tolerance = 50) {
  return (
    Math.abs(color.r - targetColor.r) <= tolerance &&
    Math.abs(color.g - targetColor.g) <= tolerance &&
    Math.abs(color.b - targetColor.b) <= tolerance
  );
}

// Funzione per capire se il colore è nel range del rosso
function isColorInRange_red(color, targetColor, tolerance = 50) {
  return (
    Math.abs(color.r - targetColor.r) <= tolerance &&
    Math.abs(color.g - targetColor.g) <= tolerance &&
    Math.abs(color.b - targetColor.b) <= tolerance
  );
}

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
        image.greyscale();
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
const readline = require("readline");

// Function to prompt user for cash value
function promptCashValue() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  return new Promise((resolve) => {
    rl.question("Enter your starting cash value: ", (answer) => {
      cash = parseFloat(answer) || 0;
      rl.close();
      resolve(cash);
    });
  });
}

// Function to capture mouse click position
function captureMouseClick(pointName) {
  return new Promise((resolve) => {
    console.log(`Click on ${pointName} and press Enter...`);

    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });

    rl.question("Press Enter after clicking: ", () => {
      // Get current mouse position
      const currentPos = mouse.getPos();
      console.log(
        `${pointName} captured at: (${currentPos.x}, ${currentPos.y})`
      );
      rl.close();
      resolve(new Point(currentPos.x, currentPos.y));
    });
  });
}

// Function to prompt for manual coordinates
function promptCoordinates(pointName, existingPoint = null) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  return new Promise((resolve) => {
    if (existingPoint) {
      rl.question(
        `Keep existing ${pointName} at (${existingPoint.x}, ${existingPoint.y})? (y/n): `,
        (answer) => {
          if (answer.toLowerCase() === "y") {
            console.log(
              `Keeping ${pointName} at: (${existingPoint.x}, ${existingPoint.y})`
            );
            rl.close();
            resolve(existingPoint);
            return;
          }
          askForCoordinates();
        }
      );
    } else {
      askForCoordinates();
    }

    function askForCoordinates() {
      rl.question(`Enter X coordinate for ${pointName}: `, (xInput) => {
        const x = parseInt(xInput.trim(), 10);
        rl.question(`Enter Y coordinate for ${pointName}: `, (yInput) => {
          const y = parseInt(yInput.trim(), 10);
          console.log(`${pointName} set at: (${x}, ${y})`);
          rl.close();
          resolve(new Point(x, y));
        });
      });
    }
  });
}

// Setup function to initialize all points
async function setupGame() {
  console.log("=== GAME SETUP ===");

  // Get cash value
  await promptCashValue();
  console.log(`Starting cash: ${cash}`);

  // Main control points
  play_collect = await promptCoordinates("PLAY/COLLECT button", play_collect);
  raise = await promptCoordinates("RAISE BET button", raise);
  lower = await promptCoordinates("LOWER BET button", lower);

  // Setup t1-t25 points
  t1 = await promptCoordinates("t1", t1);
  t2 = await promptCoordinates("t2", t2);
  t3 = await promptCoordinates("t3", t3);
  t4 = await promptCoordinates("t4", t4);
  t5 = await promptCoordinates("t5", t5);
  t6 = await promptCoordinates("t6", t6);
  t7 = await promptCoordinates("t7", t7);
  t8 = await promptCoordinates("t8", t8);
  t9 = await promptCoordinates("t9", t9);
  t10 = await promptCoordinates("t10", t10);
  t11 = await promptCoordinates("t11", t11);
  t12 = await promptCoordinates("t12", t12);
  t13 = await promptCoordinates("t13", t13);
  t14 = await promptCoordinates("t14", t14);
  t15 = await promptCoordinates("t15", t15);
  t16 = await promptCoordinates("t16", t16);
  t17 = await promptCoordinates("t17", t17);
  t18 = await promptCoordinates("t18", t18);
  t19 = await promptCoordinates("t19", t19);
  t20 = await promptCoordinates("t20", t20);
  t21 = await promptCoordinates("t21", t21);
  t22 = await promptCoordinates("t22", t22);
  t23 = await promptCoordinates("t23", t23);
  t24 = await promptCoordinates("t24", t24);
  t25 = await promptCoordinates("t25", t25);

  console.log("Setup complete! Starting game...");
}

// Funzione principale per eseguire il gioco
async function main() {
  await setupGame();
  // ...rest of your game logic...
}

main().catch(console.error);
