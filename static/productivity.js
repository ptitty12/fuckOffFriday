// static/productivity.js
const { useState, useEffect } = React;
const SimpleLineChart = () => {
  const [data, setData] = useState([]);
  const [tooltip, setTooltip] = useState({ show: false, x: 0, y: 0, value: 0, date: '' });
  
  useEffect(() => {
    fetch('/api/productivity_series')
      .then(response => response.json())
      .then(result => {
        const chartData = Object.entries(result.value).map(([date, value]) => ({
          date,
          value: value
        })).sort((a, b) => new Date(a.date) - new Date(b.date)); // Sort by date
        setData(chartData);
      })
      .catch(error => console.error('Error fetching productivity series:', error));
  }, []);

  if (data.length === 0) return null;

  // Reduced dimensions (25% of original)
  const width = 450;  // Was 600
  const height = 50;  // Was 200
  const padding = 10; // Was 20

  const maxValue = Math.max(...data.map(d => d.value));
  const minValue = Math.min(...data.map(d => d.value));

  const xScale = (index) => padding + (index * ((width - 2 * padding) / (data.length - 1)));
  const yScale = (value) => height - padding - ((value - minValue) * (height - 2 * padding) / (maxValue - minValue));

  const pathD = data.map((point, index) => 
    (index === 0 ? 'M' : 'L') + `${xScale(index)},${yScale(point.value)}`
  ).join(' ');

  return React.createElement('div', {
    className: 'relative mx-auto mb-4'  // Added margin-bottom
  }, [
    React.createElement('svg', {
      width: '100%',
      height: '100%',
      viewBox: `0 0 ${width} ${height}`,
      className: 'overflow-visible'
    }, [
      // Line
      React.createElement('path', {
        d: pathD,
        stroke: '#3b82f6',
        strokeWidth: '1.5',
        fill: 'none'
      }),
      // Date labels
      React.createElement('text', {
        x: padding,
        y: height,
        className: 'text-xs text-gray-500',
        style: { fontSize: '6px' }
      }, data[0].date),
      React.createElement('text', {
        x: width - padding,
        y: height,
        className: 'text-xs text-gray-500 text-right',
        style: { fontSize: '6px' }
      }, data[data.length - 1].date),
      // Interactive points
      ...data.map((point, index) => 
        React.createElement('circle', {
          cx: xScale(index),
          cy: yScale(point.value),
          r: '3',
          fill: 'transparent',
          stroke: 'transparent',
          className: 'cursor-pointer',
          onMouseEnter: (e) => {
            setTooltip({
              show: true,
              x: e.clientX,
              y: e.clientY,
              value: point.value,
              date: point.date
            });
          },
          onMouseLeave: () => setTooltip({ show: false }),
          key: point.date
        })
      )
    ]),
    // Tooltip
    tooltip.show && React.createElement('div', {
      className: 'absolute bg-white p-1 rounded shadow-lg text-xs',
      style: {
        left: tooltip.x,
        top: tooltip.y - 30,
        transform: 'translateX(-50%)'
      }
    }, [
      React.createElement('div', {}, tooltip.date),
      React.createElement('div', { className: 'font-bold text-blue-500' }, 
        `${tooltip.value.toFixed(1)}%`
      )
    ])
  ]);
};


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
const InfoModal = ({ isOpen, onClose }) => {
  if (!isOpen) return null;
  
  return React.createElement('div', {
    className: 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center'
  }, 
    React.createElement('div', {
      className: 'bg-white rounded-2xl p-6 max-w-md mx-4 relative shadow-xl transform transition-all',
      style: {
        background: 'linear-gradient(120deg, #f8fafc 0%, #f1f5f9 100%)'
      }
    }, [
      // Close button
      React.createElement('button', {
        className: 'absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors',
        onClick: onClose
      }, '×'),
      
      // Content
      React.createElement('div', {
        className: 'space-y-4'
      }, [
        React.createElement('h2', {
          className: 'text-xl font-semibold text-gray-800'
        }, 'Hey There :)'),
        React.createElement('p', {
          className: 'text-gray-600'
        }, 'Getting ghosted by your coworkers? Feeling unmotivated? Want to know if its just you?'),
        React.createElement('p', {
          className: 'text-gray-600'
        }, 'The novel fuck-off-friday meter analyzes search traffic for leading B2B software to determine worker productivity. Refreshed daily at 9am CST ')
      ])
    ])
  );
};



const App = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  
  return React.createElement('div', { 
    className: "flex flex-col items-center min-h-screen relative" 
  }, [
    // Icons container
    React.createElement('div', {
      className: "absolute top-4 right-4 flex gap-3 z-20" // Added gap between icons
    }, [
      // GitHub Icon
      React.createElement('a', {
        href: 'https://github.com/ptitty12',
        target: '_blank',
        className: "w-8 h-8 flex items-center justify-center rounded-full bg-white bg-opacity-80 hover:bg-opacity-100 transition-all duration-300 shadow-md"
      },
        React.createElement('div', {
          className: "text-gray-700"
        }, "🐙") // Or use "⌥" for more minimal look
      ),
      
      // Twitter Icon
      React.createElement('a', {
        href: 'https://twitter.com/patricktaylor05',
        target: '_blank',
        className: "w-8 h-8 flex items-center justify-center rounded-full bg-white bg-opacity-80 hover:bg-opacity-100 transition-all duration-300 shadow-md"
      },
        React.createElement('div', {
          className: "text-blue-400"
        }, "🐦") // Or use "𝕏" for new X logo
      ),
      
      // Info Icon (moved into the container)
      React.createElement('button', {
        className: "w-8 h-8 flex items-center justify-center rounded-full bg-white bg-opacity-80 hover:bg-opacity-100 transition-all duration-300 shadow-md",
        onClick: () => setIsModalOpen(true)
      },
        React.createElement('div', {
          className: "text-blue-500 text-xl font-semibold"
        }, "ⓘ")
      )
    ]),
    
    // Rest of your components...
    React.createElement('div', { 
      className: "absolute z-10",
      style: { top: '250px' }
    }, 
      React.createElement(SimpleLineChart)
    ),
    
    React.createElement('div', { 
      className: "flex flex-col items-center justify-center min-h-screen"
    }, 
      React.createElement(ProductivityGauge)
    ),
    
    React.createElement(InfoModal, {
      isOpen: isModalOpen,
      onClose: () => setIsModalOpen(false)
    })
  ]);
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(React.createElement(App));