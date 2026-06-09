function buildDefaultButton() {
  return {
    top: 48,
    height: 32,
    width: 96,
    left: 278
  };
}

function cacheButtonPosition() {
  let button = null;
  try {
    button = wx.getMenuButtonBoundingClientRect ? wx.getMenuButtonBoundingClientRect() : null;
  } catch (error) {
    button = null;
  }
  if (!button || !button.top || !button.height) {
    button = wx.getStorageSync("buttonPosition") || buildDefaultButton();
  }
  wx.setStorageSync("buttonPosition", button);
  return button;
}

function getButtonPositionData() {
  const button = wx.getStorageSync("buttonPosition") || buildDefaultButton();
  const top = `${button.top}px`;
  const height = `${button.height}px`;
  const width = `${button.width}px`;
  const left = `${Math.max(button.left - 30, 0)}px`;
  const navHeight = `${button.top + button.height + 8}px`;
  return {
    top,
    height,
    width,
    left,
    navHeight,
    sideWidth: width
  };
}

module.exports = {
  cacheButtonPosition,
  getButtonPositionData
};
