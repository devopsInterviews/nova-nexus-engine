import React from 'react';

const RobotFace: React.FC<{ passwordLength: number; isPasswordHidden: boolean }> = ({ passwordLength, isPasswordHidden }) => {
    const eyeAngle = Math.min(passwordLength * 5, 45);
  
    return (
      <div className="w-24 h-24 mx-auto mb-4 bg-gray-700 rounded-full flex items-center justify-center relative">
        <div className="flex space-x-4">
          <div className="w-6 h-6 bg-white rounded-full flex items-center justify-center" style={{ transform: `translateX(${-eyeAngle / 4}px)` }}>
            <div className="w-3 h-3 bg-black rounded-full" style={{ transform: `translateX(${eyeAngle / 8}px)` }}></div>
          </div>
          <div className="w-6 h-6 bg-white rounded-full flex items-center justify-center" style={{ transform: `translateX(${eyeAngle / 4}px)` }}>
            <div className="w-3 h-3 bg-black rounded-full" style={{ transform: `translateX(${eyeAngle / 8}px)` }}></div>
          </div>
        </div>
        {isPasswordHidden && (
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-8 bg-gray-600 rounded-full flex items-center justify-center">
            <span className="text-white text-xs">Shhh!</span>
          </div>
        )}
      </div>
    );
  };

  export default RobotFace;
