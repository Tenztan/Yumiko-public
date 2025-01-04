	function eventWindowLoaded() {
	    canvasApp()
	}

	function canvasSupport(n) {
	    return !!n.getContext
	}

	function canvasApp() {
	    var n = document.getElementById("jc");
	    if (canvasSupport(jc)) {
	        var e = n.getContext("2d"),
	            t = n.width = window.innerWidth,
	            a = n.height = window.innerHeight,
	            i = Array(275).join(0).split("");
	        "undefined" != typeof Game_Interval && clearInterval(Game_interval), Game_Interval = setInterval(o, 45)
	    }

	    function o() {
	        e.fillStyle = "rgba(0,0,0,.07)",
          e.fillRect(0, 0, t, a),
          e.fillStyle = "#8a8580",
          e.font = "10px Georgia",
          i.map(function(n, t) {
	            text = String.fromCharCode(100 + 33 * Math.random()),
              x = 10 * t,
              e.fillText(text, x, n),
              n > 100 + 3e4 * Math.random() ? i[t] = 0 : i[t] = n + 10
	        })
	    }
	}
	window.addEventListener("load", eventWindowLoaded, !1);
var words = [
  'Yumiko',
  'ai',
  'Yumiko ai'

];
var letters = "abcdefghijklmnopqrstuvwxyz#%&^+=-",
    speed = 250,
    steps = 4,
    loader = document.querySelector('#loader');

function getRandomWord() {
  var randomWord = words[Math.floor(Math.random() * words.length)];
  return randomWord;
}
function getRandomLetter() {
  var randomLetter = letters[Math.floor(Math.random() * letters.length)];
  return randomLetter;
}

function randomWordLoop() {
  var word = getRandomWord();
  var textLength = word.length;
  for(var i = 0; i < textLength; i++) {
    (function(i,word){
      letterAppear(i, word);
    })(i,word)
  }

  function letterAppear(i, word) {
    setTimeout(function() {
      randomLetters(i, word);
    }, speed*i);
  }

  function randomLetters(i, word) {
    for (var j = 0; j <= steps; j++) {
      charsAnim(i, word, j);
    }
  }

  function charsAnim(i, word, j) {
    setTimeout(function() {
      var count = j;
      if (j < steps) {
        randomChar(i, word, count, j);
      } else {
        goodChar(i, word, count, j);
      }
      /* seems it fails less if I divide j, don't know why */
      /*}, (speed/steps)*(j / 1.8));*/
    }, ((speed/steps)*j) - (speed/steps));
  }

  function randomChar(i, word, count, j) {
    var letter = getRandomLetter();
    if (j > 0) {
      var oldText = loader.textContent.slice(0, -1);
    } else {
      var oldText = loader.textContent;
    }
    loader.textContent = oldText + letter;
  }
  function goodChar(i, word, count, j) {
    var oldText = loader.textContent.slice(0, -1);
    loader.textContent = oldText + word[i];
    if (i == textLength - 1 ) {
      removeWord();
    }
  }

  function removeWord() {
    setTimeout(function() {
      for (var k = 0; k < textLength; k++) {
         removeLetters(k);
      }
    }, speed*2);
  }
  function removeLetters(k) {
    setTimeout(function() {
      removeLetter(k);
    }, 75*k);
  }
  function removeLetter(k) {
    var actualText = loader.textContent.slice(0, -1);
    loader.textContent = actualText;
    if (k == textLength - 1) {
      randomWordLoop();
    }
  }
}

randomWordLoop();



