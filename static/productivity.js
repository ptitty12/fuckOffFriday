// Use React from global scope
const { useState, useEffect, useRef } = React;

const SimpleBarChart = () => {
  const [data, setData] = useState([]);
  const [tooltip, setTooltip] = useState({ show: false, x: 0, y: 0, value: 0, date: '' });
  const chartRef = useRef(null);
  
  useEffect(() => {
    fetch('/api/productivity_series')
      .then(response => response.json())
      .then(result => {
        const chartData = Object.entries(result.value).map(([date, value]) => {
          const dateObj = new Date(date + 'T12:00:00');
          return {
            date,
            value: value,
            dayOfWeek: dateObj.getDay(),
            dayName: dateObj.toLocaleDateString('en-US', { weekday: 'long', timeZone: 'UTC' })
          };
        }).sort((a, b) => new Date(a.date) - new Date(b.date));
        
        setData(chartData);
      })
      .catch(error => console.error('Error fetching productivity series:', error));
  }, []);

  if (data.length === 0) return null;

  const width = 450;
  const height = 50;
  const padding = 10;
  const barPadding = 1;
  const barWidth = ((width - 2 * padding) / data.length) - barPadding;

  const maxValue = Math.max(...data.map(d => d.value));
  const minValue = Math.min(...data.map(d => d.value));

  const xScale = (index) => padding + (index * (barWidth + barPadding));
  const yScale = (value) => height - padding - ((value - minValue) * (height - 2 * padding) / (maxValue - minValue));

  const now = new Date();
  const currentDayOfWeek = now.getDay();
  
  const today = new Date().toLocaleDateString('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).split('/').reverse().join('-');

  const shouldHighlight = (point) => {
    const pointDate = new Date(point.date + 'T12:00:00');
    const pointDateString = pointDate.toLocaleDateString('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).split('/').reverse().join('-');
    
    if (pointDateString === today) {
      return true;
    }
    
    return pointDate < now && point.dayOfWeek === currentDayOfWeek;
  };

  return React.createElement('div', {
    ref: chartRef,
    className: "relative mx-auto mb-4"
  }, [
    React.createElement('svg', {
      width: "100%",
      height: "100%",
      viewBox: `0 0 ${width} ${height}`,
      className: "overflow-visible"
    }, [
      ...data.map((point, index) => 
        React.createElement('rect', {
          key: point.date,
          x: xScale(index),
          y: yScale(point.value),
          width: barWidth,
          height: height - padding - yScale(point.value),
          fill: shouldHighlight(point) ? '#22c55e' : '#3b82f6',
          className: "cursor-pointer transition-colors duration-200 hover:opacity-80",
          onMouseEnter: (e) => {
            const rect = chartRef.current.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            setTooltip({
              show: true,
              x,
              y,
              value: point.value,
              date: `${point.date} (${point.dayName})`
            });
          },
          onMouseLeave: () => setTooltip({ show: false })
        })
      ),
      React.createElement('text', {
        x: padding,
        y: height,
        className: "text-xs text-gray-500",
        style: { fontSize: '6px' }
      }, data[0].date),
      React.createElement('text', {
        x: width - padding,
        y: height,
        className: "text-xs text-gray-500 text-right",
        style: { fontSize: '6px' }
      }, data[data.length - 1].date)
    ]),
    tooltip.show && React.createElement('div', {
      className: "absolute bg-white p-1 rounded shadow-lg text-xs pointer-events-none",
      style: {
        position: 'absolute',
        left: tooltip.x + 'px',
        top: (tooltip.y - 10) + 'px',
        transform: 'translate(-50%, -100%)',
        pointerEvents: 'none'
      }
    }, [
      React.createElement('div', {}, tooltip.date),
      React.createElement('div', {
        className: "font-bold text-blue-500"
      }, `${tooltip.value.toFixed(1)}%`)
    ])
  ]);
};


const ProductivityGauge = () => {
  const [targetValue, setTargetValue] = useState(0);
  const [displayValue, setDisplayValue] = useState(0);
  const [isAnimating, setIsAnimating] = useState(true);
  
  useEffect(() => {
    fetch('/api/productivity')
      .then(response => response.json())
      .then(data => {
        setTargetValue(data.value * 100);
      })
      .catch(error => console.error('Error fetching productivity:', error));
  }, []);
  
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
    }, [
      React.createElement('div', { 
        className: "relative" 
      }, [
        React.createElement('div', {
          className: `text-8xl font-bold ${text} transition-all duration-300`
        }, `${displayValue > 0 ? '+' : ''}${displayValue.toFixed(1)}%`),
        
        React.createElement('div', {
          className: "absolute right-0 top-0 transform translate-x-full -translate-y-1/4"
        }, [
          displayValue > 0 && React.createElement('div', {
            className: `text-6xl ${text} ${isAnimating ? 'animate-bounce' : ''}`
          }, "↑"),
          displayValue < 0 && React.createElement('div', {
            className: `text-6xl ${text} ${isAnimating ? 'animate-bounce' : ''}`
          }, "↓")
        ])
      ]),
      
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
    ])
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
      React.createElement('button', {
        className: 'absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors',
        onClick: onClose
      }, '×'),
      
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
        }, 'The novel fuck-off-friday meter analyzes search traffic for leading B2B software to determine worker productivity. Refreshed daily at 9am CST')
      ])
    ])
  );
};

// Update App component to use SimpleBarChart
const App = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  
  return React.createElement('div', { 
    className: "flex flex-col items-center min-h-screen relative" 
  }, [
    // Icons container
    React.createElement('div', {
      className: "absolute top-4 right-4 flex gap-3 z-20"
    }, [
      React.createElement('a', {
        href: 'https://github.com/ptitty12',
        target: '_blank',
        className: "w-8 h-8 flex items-center justify-center rounded-full bg-white bg-opacity-80 hover:bg-opacity-100 transition-all duration-300 shadow-md"
      },
        React.createElement('div', {
          className: "text-gray-700"
        }, "🐙")
      ),
      React.createElement('a', {
        href: 'https://twitter.com/patricktaylor05',
        target: '_blank',
        className: "w-8 h-8 flex items-center justify-center rounded-full bg-white bg-opacity-80 hover:bg-opacity-100 transition-all duration-300 shadow-md"
      },
        React.createElement('div', {
          className: "text-blue-400"
        }, "🐦")
      ),
      React.createElement('button', {
        className: "w-8 h-8 flex items-center justify-center rounded-full bg-white bg-opacity-80 hover:bg-opacity-100 transition-all duration-300 shadow-md",
        onClick: () => setIsModalOpen(true)
      },
        React.createElement('div', {
          className: "text-blue-500 text-xl font-semibold"
        }, "ⓘ")
      )
    ]),
    
    React.createElement('div', { 
      className: "absolute z-10",
      style: { top: '250px' }
    }, 
      React.createElement(SimpleBarChart)
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