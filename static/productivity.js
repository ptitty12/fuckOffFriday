// static/productivity.js
const { useState, useEffect } = React;

const ProductivityGauge = () => {
  const [targetValue, setTargetValue] = useState(0);
  const [displayValue, setDisplayValue] = useState(0);
  const [isAnimating, setIsAnimating] = useState(true);
  
  // Fetch the actual value from the API
  useEffect(() => {
    fetch('/api/productivity')
      .then(response => response.json())
      .then(data => {
        setTargetValue(data.value * 100); // Multiply by 100 to convert to percentage
      })
      .catch(error => console.error('Error fetching productivity:', error));
  }, []);
  
  // Animation effect
  useEffect(() => {
    const duration = 2000;
    const steps = 60;
    const stepDuration = duration / steps;
    const increment = targetValue / steps;
    let currentStep = 0;
    
    const timer = setInterval(() => {
      if (currentStep < steps) {
        setDisplayValue(prev => {
          const next = Math.round((currentStep + 1) * increment * 10) / 10;
          return targetValue > 0 ? Math.min(next, targetValue) : Math.max(next, targetValue);
        });
        currentStep++;
      } else {
        setIsAnimating(false);
        clearInterval(timer);
      }
    }, stepDuration);

    return () => clearInterval(timer);
  }, [targetValue]);

  const getColors = (value) => {
    if (value > 0) return { text: 'text-green-500', bg: 'bg-green-100' };
    if (value < 0) return { text: 'text-red-500', bg: 'bg-red-100' };
    return { text: 'text-blue-500', bg: 'bg-blue-100' };
  };

  const { text, bg } = getColors(displayValue);

  return React.createElement('div', {
    className: "flex flex-col items-center justify-center min-h-screen"
  }, 
    React.createElement('div', {
      className: `p-8 rounded-2xl ${bg} transition-all duration-500`
    },
      React.createElement('div', { className: "relative" },
        React.createElement('div', {
          className: `text-8xl font-bold ${text} transition-all duration-300`
        }, `${displayValue > 0 ? '+' : ''}${displayValue.toFixed(1)}%`),
        
        React.createElement('div', {
          className: "absolute right-0 top-0 transform translate-x-full -translate-y-1/4"
        },
          displayValue > 0 && React.createElement('div', {
            className: `text-6xl ${text} ${isAnimating ? 'animate-bounce' : ''}`
          }, "↑"),
          displayValue < 0 && React.createElement('div', {
            className: `text-6xl ${text} ${isAnimating ? 'animate-bounce' : ''}`
          }, "↓")
        )
      ),
      
      React.createElement('div', {
        className: `text-xl mt-4 ${text} text-center font-medium`
      },
        displayValue === 0 ? "Average Productivity" :
        displayValue > 0 ? "Above Average Productivity" :
        "Below Average Productivity"
      ),
      
      React.createElement('div', {
        className: `absolute inset-0 rounded-2xl ${text} opacity-50 ${isAnimating ? 'animate-pulse' : ''}`,
        style: {
          border: '2px solid currentColor',
          transform: 'scale(1.05)',
          zIndex: -1
        }
      })
    )
  );
};

// Render the component
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(React.createElement(ProductivityGauge));