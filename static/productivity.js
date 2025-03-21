// Use React from global scope
const { useState, useEffect, useRef } = React;

const SimpleBarChart = () => {
  const [data, setData] = useState([]);
  const [tooltip, setTooltip] = useState({ show: false, x: 0, y: 0, value: 0, percentChange: 0, date: '' });
  const chartRef = useRef(null);
  
  useEffect(() => {
    fetch('/api/productivity_series')
      .then(response => response.json())
      .then(result => {
        console.log("API result:", result); // Debug log to see the structure
        
        const chartData = Object.entries(result.value).map(([date, dataObj]) => {
          const dateObj = new Date(date + 'T12:00:00');
          return {
            date,
            value: dataObj.value, // Access the value property
            percentChange: dataObj.percent_change, // Store percent_change
            dayOfWeek: dateObj.getDay(),
            dayName: dateObj.toLocaleDateString('en-US', { weekday: 'long', timeZone: 'UTC' })
          };
        }).sort((a, b) => new Date(a.date) - new Date(b.date));
        
        console.log("Processed chart data:", chartData); // Debug log
        setData(chartData);
      })
      .catch(error => console.error('Error fetching productivity series:', error));
  }, []);

  if (data.length === 0) return null;

  const width = 2400;
  const height = 500;
  const padding = 10;
  const barPadding = 1;
  const barWidth = 30;
  
  // Calculate how many bars we can fit in the chart
  const maxBars = Math.floor((width - 2 * padding) / (barWidth + barPadding));
  
  // If we have more data points than can fit, only show the most recent ones
  const visibleData = data.length > maxBars ? data.slice(-maxBars) : data;
  
  // Center the chart by calculating the starting X position
  const totalBarsWidth = visibleData.length * (barWidth + barPadding) - barPadding;
  const startX = (width - totalBarsWidth) / 2;

  const maxValue = Math.max(...visibleData.map(d => d.value));
  const minValue = Math.min(...visibleData.map(d => d.value));

  const xScale = (index) => startX + (index * (barWidth + barPadding));
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
      ...visibleData.map((point, index) => 
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
              percentChange: point.percentChange,
              date: `${point.date} (${point.dayName})`
            });
          },
          onMouseLeave: () => setTooltip({ show: false })
        })
      ),
      React.createElement('text', {
        x: startX,
        y: height,
        className: "text-xs text-gray-500",
        style: { fontSize: '12px' }
      }, visibleData[0].date),
      React.createElement('text', {
        x: xScale(visibleData.length - 1) + barWidth,
        y: height,
        className: "text-xs text-gray-500 text-right",
        style: { fontSize: '12px' }
      }, visibleData[visibleData.length - 1].date)
    ]),
    tooltip.show && React.createElement('div', {
      className: "absolute bg-white p-2 rounded shadow-lg text-sm pointer-events-none",
      style: {
        left: tooltip.x + 'px',
        top: (tooltip.y - 15) + 'px',
        transform: 'translate(-50%, -100%)',
        pointerEvents: 'none'
      }
    }, [
      React.createElement('div', {}, tooltip.date),
      React.createElement('div', {
        className: "font-bold text-blue-500"
      }, `Value: ${tooltip.value.toFixed(1)}`),
      React.createElement('div', {
        className: tooltip.percentChange >= 0 ? "font-bold text-green-500" : "font-bold text-red-500"
      }, `vs Same Day: ${tooltip.percentChange >= 0 ? '+' : ''}${tooltip.percentChange.toFixed(1)}%`)
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
  ]);
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

const App = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  
  return React.createElement('div', { 
    className: "h-screen overflow-hidden"
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
    
    // Main content with fixed positioning
    React.createElement('div', { 
      className: "fixed inset-0 flex items-center justify-center"
    }, 
      React.createElement('div', { 
        className: "relative"
      }, [
        // Bar chart positioned above the gauge
        React.createElement('div', { 
          className: "absolute left-1/2 transform -translate-x-1/2 -translate-y-6"
        }, 
          React.createElement(SimpleBarChart)
        ),
        
        // Productivity gauge
        React.createElement('div', {}, 
          React.createElement(ProductivityGauge)
        )
      ])
    ),
    
    React.createElement(InfoModal, {
      isOpen: isModalOpen,
      onClose: () => setIsModalOpen(false)
    })
  ]);
};

// Create root and render
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(React.createElement(App));