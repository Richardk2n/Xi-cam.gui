# -*- coding: utf-8 -*-
from functools import WRAPPER_ASSIGNMENTS
from pyqtgraph import ImageView, InfiniteLine, mkPen, ScatterPlotItem, ImageItem, PlotItem
from qtpy.QtGui import QTransform, QPolygonF
from qtpy.QtWidgets import QLabel, QErrorMessage, QSizePolicy, QPushButton
from qtpy.QtCore import Qt, Signal, Slot, QSize, QPointF, QRectF
import numpy as np

# from pyFAI.geometry import Geometry
from xicam.gui.widgets.elidedlabel import ElidedLabel
from xicam.gui.widgets.ROI import BetterPolyLineROI
from xicam.core import msg
import enum


# from pyFAI import AzimuthalIntegrator


# NOTE: PyQt widget mixins have pitfalls; note #2 here: http://trevorius.com/scrapbook/python/pyqt-multiple-inheritance/

# NOTE: PyFAI geometry position vector is: x = up
#                                          y = right
#                                          z = beam

# TODO: Add notification when qgrid is very wrong


def q_from_angles(phi, alpha, wavelength):
    r = 2 * np.pi / wavelength
    qx = r * np.sin(phi) * np.cos(alpha)
    qy = r * np.cos(phi) * np.sin(alpha)
    qz = r * (np.cos(phi) * np.cos(alpha) - 1)

    return np.array([qx, qy, qz])


def alpha(x, y, z):
    return np.arctan2(y, z)


def phi(x, y, z):
    return np.arctan2(x, z)


class DisplayMode(enum.Enum):
    raw = enum.auto
    cake = enum.auto
    remesh = enum.auto


class PixelSpace(ImageView):
    def __init__(self, *args, **kwargs):
        # Add axes
        self.axesItem = PlotItem()
        self.axesItem.axes["left"]["item"].setZValue(10)
        self.axesItem.axes["top"]["item"].setZValue(10)
        if "view" not in kwargs:
            kwargs["view"] = self.axesItem

        self._transform = QTransform()

        super(PixelSpace, self).__init__(*args, **kwargs)

        self.imageItem.sigImageChanged.connect(self.updateAxes)

    def transform(self, img=None):
        # Build Quads
        shape = img.shape
        a = [(0, shape[-2] - 1), (shape[-1] - 1, shape[-2] - 1), (shape[-1] - 1, 0), (0, 0)]

        b = [(0, 0), (shape[-1] - 1, 0), (shape[-1] - 1, shape[-2] - 1), (0, shape[-2] - 1)]

        quad1 = QPolygonF()
        quad2 = QPolygonF()
        for p, q in zip(a, b):
            quad1.append(QPointF(*p))
            quad2.append(QPointF(*q))

        transform = QTransform()
        QTransform.quadToQuad(quad1, quad2, transform)

        for item in self.view.items:
            if isinstance(item, ImageItem):
                item.setTransform(transform)
        self._transform = transform
        return img, transform

    def setImage(self, img, *args, **kwargs):
        if img is None:
            return

        if not kwargs.get("transform", None):
            img, transform = self.transform(img)
            self.updateAxes()
            super(PixelSpace, self).setImage(img, *args, transform=transform, **kwargs)

        else:
            super(PixelSpace, self).setImage(img, *args, **kwargs)

    def setTransform(self):
        self.setImage(self.imageItem.image)  # this should loop back around to the respective transforms

    def updateAxes(self):
        self.axesItem.setLabel("bottom", "x (px)")  # , units='s')
        self.axesItem.setLabel("left", "z (px)")


class QSpace(PixelSpace):
    def __init__(self, *args, geometry=None, **kwargs):
        self.displaymode = DisplayMode.raw

        super(QSpace, self).__init__(*args, **kwargs)

        self._geometry = None  # type: AzimuthalIntegrator
        self.setGeometry(geometry)

    def setGeometry(self, geometry):
        if callable(geometry):
            geometry = geometry()
        self._geometry = geometry
        self.setTransform()


class EwaldCorrected(QSpace):
    def setDisplayMode(self, mode):
        self.displaymode = mode
        self.setTransform()

    def transform(self, img):
        if not self._geometry:
            return super(EwaldCorrected, self).transform(img)  # Do pixel space transform when not calibrated

        from camsaxs import remesh_bbox

        img, q_x, q_z = remesh_bbox.remesh(np.squeeze(img), self._geometry, reflection=False, alphai=None)

        # Build Quads
        shape = img.shape
        a = 0, shape[-2] - 1
        b = shape[-1] - 1, shape[-2] - 1
        c = shape[-1] - 1, 0
        d = 0, 0

        quad1 = QPolygonF()
        quad2 = QPolygonF()
        for p, q in zip([a, b, c, d], [a, b, c, d]):  # the zip does the flip :P
            quad1.append(QPointF(*p))
            quad2.append(QPointF(q_x[q[::-1]], q_z[q[::-1]]))

        transform = QTransform()
        QTransform.quadToQuad(quad1, quad2, transform)

        for item in self.view.items:
            if isinstance(item, ImageItem):
                item.setTransform(transform)
        self._transform = transform

        return img, self._transform

    def setImage(self, img, *args, **kwargs):
        if img is None:
            return

        if self._geometry:
            img, transform = self.transform(img)
            self.axesItem.setLabel("bottom", "q_x (Å⁻¹)")  # , units='s')
            self.axesItem.setLabel("left", "q_z (Å⁻¹)")
            super(EwaldCorrected, self).setImage(img, *args, transform=transform, **kwargs)

        else:
            super(EwaldCorrected, self).setImage(img, *args, **kwargs)


class CenterMarker(QSpace):
    def __init__(self, *args, **kwargs):
        self.centerplot = ScatterPlotItem(brush="r")
        self.centerplot.setZValue(100)

        super(CenterMarker, self).__init__(*args, **kwargs)

        self.addItem(self.centerplot)
        self.drawCenter()

    def drawCenter(self):
        try:
            fit2d = self._geometry.getFit2D()
        except (TypeError, AttributeError):
            pass
        else:
            x = fit2d['centerX']
            y = fit2d['centerY']
            self.centerplot.setData(x=[x], y=[y])

    def setGeometry(self, geometry):
        super(CenterMarker, self).setGeometry(geometry)
        self.drawCenter()


class Crosshair(ImageView):
    def __init__(self, *args, **kwargs):
        super(Crosshair, self).__init__(*args, **kwargs)
        linepen = mkPen("#FFA500")
        self._vline = InfiniteLine((0, 0), angle=90, movable=False, pen=linepen)
        self._hline = InfiniteLine((0, 0), angle=0, movable=False, pen=linepen)

        self._vline.setVisible(False)
        self._hline.setVisible(False)

        self.addItem(self._vline)
        self.addItem(self._hline)

        self.scene.sigMouseMoved.connect(self.moveCrosshair)

    def moveCrosshair(self, pos):
        if self.view.getViewBox().sceneBoundingRect().contains(pos):
            mousePoint = self.view.getViewBox().mapSceneToView(pos)
            x, y = mousePoint.x(), mousePoint.y()

            if self.imageItem.mapRectToView(self.imageItem.boundingRect()).contains(mousePoint):  # within bounds
                self._vline.setPos(x)
                self._hline.setPos(y)
                self._hline.setVisible(True)
                self._vline.setVisible(True)
            else:
                self._hline.setVisible(False)
                self._vline.setVisible(False)


class PixelCoordinates(PixelSpace):
    def __init__(self, *args, **kwargs):
        super(PixelCoordinates, self).__init__(*args, **kwargs)

        self._coordslabel = QLabel(
            "<div style='font-size:12pt;background-color:#111111; " "text-overflow: ellipsis; width:100%;'>&nbsp;</div>"
        )

        # def sizeHint():
        #     sizehint = QSize(self.ui.graphicsView.width()-10, self._coordslabel.height())
        #     return sizehint
        # self._coordslabel.sizeHint = sizeHint
        self._coordslabel.setSizePolicy(
            QSizePolicy.Ignored, QSizePolicy.Ignored
        )  # TODO: set sizehint to take from parent, not text
        self.ui.gridLayout.addWidget(self._coordslabel, 2, 0, 1, 1, alignment=Qt.AlignHCenter)

        self.scene.sigMouseMoved.connect(self.displayCoordinates)

    def displayCoordinates(self, pos):
        if self.view.sceneBoundingRect().contains(pos):
            mousePoint = self.view.getViewBox().mapSceneToView(pos)
            pos = QPointF(mousePoint.x(), mousePoint.y())

            if self.imageItem.mapRectToView(self.imageItem.boundingRect()).contains(mousePoint):  # within bounds
                # angstrom=QChar(0x00B5)
                pxpos = self.imageItem.mapFromView(pos)

                self.formatCoordinates(pxpos, pos)
            else:
                self._coordslabel.setText("<div style='font-size:12pt;background-color:#111111;'>&nbsp;</div>")

    def formatCoordinates(self, pxpos, pos):
        """
        when the mouse is moved in the viewer, recalculate coordinates
        """

        try:
            I = self.imageItem.image[int(pxpos.y()), int(pxpos.x())]
        except IndexError:
            I = 0

        self._coordslabel.setText(
            f"<div style='font-size: 12pt;background-color:#111111; color:#FFFFFF;"
            f"text-overflow: ellipsis; width:100%;'>"
            f"x={pxpos.x():0.1f}, "
            f"<span style=''>y={self.imageItem.image.shape[-2] - pxpos.y():0.1f}</span>, "
            f"<span style=''>I={I:0.0f}</span></div>"
        )


class QCoordinates(QSpace, PixelCoordinates):
    def formatCoordinates(self, pxpos, pos):
        """
        when the mouse is moved in the viewer, recalculate coordinates
        """

        try:
            I = self.imageItem.image[int(pxpos.y()), int(pxpos.x())]
        except IndexError:
            I = 0
        self._coordslabel.setText(
            f"<div style='font-size: 12pt;background-color:#111111; color:#FFFFFF; "
            f"text-overflow: ellipsis; width:100%;'>"
            f"x={pxpos.x():0.1f}, "
            f"<span style=''>y={self.imageItem.image.shape[-2] - pxpos.y():0.1f}</span>, "
            f"<span style=''>I={I:0.0f}</span>, "
            f"q={np.sqrt(pos.x() ** 2 + pos.y() ** 2):0.3f} \u212B\u207B\u00B9, "
            f"q<sub>z</sub>={pos.y():0.3f} \u212B\u207B\u00B9, "
            f"q<sub>\u2225</sub>={pos.x():0.3f} \u212B\u207B\u00B9, "
            f"d={2 * np.pi / np.sqrt(pos.x() ** 2 + pos.y() ** 2) * 10:0.3f} nm, "
            f"\u03B8={np.rad2deg(np.arctan2(pos.y(), pos.x())):.2f}&#176;</div>"
        )


class BetterButtons(ImageView):
    def __init__(self, *args, **kwargs):
        super(BetterButtons, self).__init__(*args, **kwargs)

        # Setup axes reset button
        self.resetAxesBtn = QPushButton("Reset Axes")
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.resetAxesBtn.sizePolicy().hasHeightForWidth())
        self.resetAxesBtn.setSizePolicy(sizePolicy)
        self.resetAxesBtn.setObjectName("resetAxes")
        self.ui.gridLayout.addWidget(self.resetAxesBtn, 2, 1, 1, 1)
        self.resetAxesBtn.clicked.connect(self.autoRange)

        # Setup LUT reset button
        self.resetLUTBtn = QPushButton("Reset LUT")
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.resetLUTBtn.sizePolicy().hasHeightForWidth())
        # self.resetLUTBtn.setSizePolicy(sizePolicy)
        # self.resetLUTBtn.setObjectName("resetLUTBtn")
        self.ui.gridLayout.addWidget(self.resetLUTBtn, 2, 2, 1, 1)
        self.resetLUTBtn.clicked.connect(self.autoLevels)

        # Hide ROI button and rearrange
        self.ui.roiBtn.setParent(None)
        self.ui.menuBtn.setParent(None)
        # self.ui.gridLayout.addWidget(self.ui.menuBtn, 1, 1, 1, 1)
        self.ui.gridLayout.addWidget(self.ui.graphicsView, 0, 0, 2, 1)


class PolygonROI(ImageView):
    def __init__(self, *args, **kwargs):
        """
        Image view extended with an adjustable polygon region-of-interest (ROI).

        When first displayed, the polygon ROI's corners will be set to the image item's corners.

        Parameters
        ----------
        args, optional
            Positional arguments for the ImageView.
        kwargs, optional
            Keyword arguments for the ImageView.
        """
        super(PolygonROI, self).__init__(*args, **kwargs)
        rect = self.imageItem.boundingRect()  # type: QRectF
        positions = [
            (rect.bottomLeft().x(), rect.bottomLeft().y()),
            (rect.bottomRight().x(), rect.bottomRight().y()),
            (rect.topRight().x(), rect.topRight().y()),
            (rect.topLeft().x(), rect.topLeft().y()),
        ]
        self._roiItem = BetterPolyLineROI(positions=positions, closed=True, scaleSnap=True, translateSnap=True)
        self.addItem(self._roiItem)

    def __repr__(self):
        return type(self).__name__ + repr(self._roiItem)

    def poly_mask(self):
        """
        Gets the mask array for a ROI polygon on the image.

        The mask array's shape will match the image's shape.
        Any pixel inside both the ROI polygon and the image will be set to 1 in the mask array;
        all other values in the mask will be set to 0.

        Returns
        -------
        ndarray:
            Mask array of the ROI polygon within image space (mask shape matches image shape).

        """
        result, mapped = self._roiItem.getArrayRegion(
            np.ones_like(self.imageItem.image), self.imageItem, returnMappedCoords=True
        )

        # TODO -- move this code to own function and test
        # Reverse the result array to make indexing calculations easier, then revert back
        result = result[::-1, ::-1]
        mapped = mapped[::-1, ::-1]

        # Pad result mask rect into bounding rect of mask and image
        floorRow = np.floor(mapped[0]).astype(int)
        floorCol = np.floor(mapped[1]).astype(int)

        # Return empty mask if ROI bounding box does not intersect image bounding box
        resultRect = QRectF(QPointF(np.min(floorRow), np.min(floorCol)), QPointF(np.max(floorRow), np.max(floorCol)))
        if not self._intersectsImage(resultRect):
            # TODO -- is zeros(shape) the right return value for a non-intersecting polygon?
            return np.zeros(self.imageItem.image.shape)

        # Find the bounds of the ROI polygon
        minX = np.min(floorRow)
        maxX = np.max(floorRow)
        minY = np.min(floorCol)
        maxY = np.max(floorCol)

        width = self.imageItem.width()
        height = self.imageItem.height()
        # Pad the ROI polygon into the image shape
        # Don't need padding if a polygon boundary is outside of the image shape
        padXBefore = minX
        if minX < 0:
            padXBefore = 0
        padXAfter = height - maxX
        if padXAfter < 0:
            padXAfter = 0
        padYBefore = minY
        if minY < 0:
            padYBefore = 0
        padYAfter = width - maxY
        if padYAfter < 0:
            padYAfter = 0

        boundingBox = np.pad(result, ((padYBefore, padYAfter), (padXBefore, padXAfter)), "constant")

        # For trimming, any negative minimums need to be shifted into the image shape
        offsetX = 0
        offsetY = 0
        if minX < 0:
            offsetX = abs(minX)
        if minY < 0:
            offsetY = abs(minY)
        trimmed = boundingBox[abs(offsetY) : abs(offsetY) + height, abs(offsetX) : abs(offsetX) + width]

        # Reorient the trimmed mask array
        trimmed = trimmed[::-1, ::-1]

        # # TODO remove plotting code below
        # from matplotlib import pyplot as plt
        # plt.figure('bounding_box, origin="lower"')
        # plt.imshow(boundingBox, origin='lower')
        # plt.show()
        #
        #
        # plt.figure(f'trimmed, origin="lower", [{abs(offsetY)}:{abs(offsetY)+height}, {abs(offsetX)}:{abs(offsetX)+width}]')
        # plt.imshow(trimmed, origin='lower')
        # plt.show()
        # # TODO remove the plotting code above
        return trimmed

    def _intersectsImage(self, rectangle: QRectF):
        """
        Checks if a rectangle intersects the image's bounding rectangle.

        Parameters
        ----------
        rectangle
            Rectangle to test intersection with the image item's bounding rectangle.

        Returns
        -------
        bool
            True if the rectangle and the image bounding rectangle intersect; otherwise False.

        """
        # TODO -- test
        return self.imageItem.boundingRect().intersects(rectangle)


import collections
from pyqtgraph import functions as fn
from pyqtgraph import debug
from pyqtgraph import Point


class LogScaleImageItem(ImageItem):
    def __init__(self, *args, **kwargs):
        super(LogScaleImageItem, self).__init__(*args, **kwargs)
        self.logScale = True

    def render(self):
        # Convert data to QImage for display.

        profile = debug.Profiler()
        if self.image is None or self.image.size == 0:
            return
        if isinstance(self.lut, collections.Callable):
            lut = self.lut(self.image)
        else:
            lut = self.lut

        if self.logScale:
            image = self.image + 1
            with np.errstate(invalid="ignore"):
                image = image.astype(np.float)
                np.log(image, where=image >= 0, out=image)  # map to 0-255
        else:
            image = self.image

        if self.autoDownsample:
            # reduce dimensions of image based on screen resolution
            o = self.mapToDevice(QPointF(0, 0))
            x = self.mapToDevice(QPointF(1, 0))
            y = self.mapToDevice(QPointF(0, 1))
            w = Point(x - o).length()
            h = Point(y - o).length()
            if w == 0 or h == 0:
                self.qimage = None
                return
            xds = max(1, int(1.0 / w))
            yds = max(1, int(1.0 / h))
            axes = [1, 0] if self.axisOrder == "row-major" else [0, 1]
            image = fn.downsample(image, xds, axis=axes[0])
            image = fn.downsample(image, yds, axis=axes[1])
            self._lastDownsample = (xds, yds)
        else:
            pass

        # if the image data is a small int, then we can combine levels + lut
        # into a single lut for better performance
        levels = self.levels
        if levels is not None and levels.ndim == 1 and image.dtype in (np.ubyte, np.uint16):
            if self._effectiveLut is None:
                eflsize = 2 ** (image.itemsize * 8)
                ind = np.arange(eflsize)
                minlev, maxlev = levels
                levdiff = maxlev - minlev
                levdiff = 1 if levdiff == 0 else levdiff  # don't allow division by 0
                if lut is None:
                    efflut = fn.rescaleData(ind, scale=255.0 / levdiff, offset=minlev, dtype=np.ubyte)
                else:
                    lutdtype = np.min_scalar_type(lut.shape[0] - 1)
                    efflut = fn.rescaleData(
                        ind, scale=(lut.shape[0] - 1) / levdiff, offset=minlev, dtype=lutdtype, clip=(0, lut.shape[0] - 1)
                    )
                    efflut = lut[efflut]

                self._effectiveLut = efflut
            lut = self._effectiveLut
            levels = None

        # Assume images are in column-major order for backward compatibility
        # (most images are in row-major order)

        if self.axisOrder == "col-major":
            image = image.transpose((1, 0, 2)[: image.ndim])

        if self.logScale:
            with np.errstate(invalid="ignore"):
                levels = np.log(np.add(levels, 1))
            levels[0] = np.nanmax([levels[0], 0])

        argb, alpha = fn.makeARGB(image, lut=lut, levels=levels)
        self.qimage = fn.makeQImage(argb, alpha, transpose=False)


class LogScaleIntensity(ImageView):
    def __init__(self, *args, **kwargs):
        if kwargs.get("imageItem") and not isinstance(kwargs.get("imageItem"), LogScaleImageItem):
            raise RuntimeError("The imageItem set to a LogScaleIntensity ImageView must be a LogScaleImageItem.")

        kwargs["imageItem"] = LogScaleImageItem()
        super(LogScaleIntensity, self).__init__(*args, **kwargs)

        self.logScale = True

        # Setup log scale button
        self.logIntensityButton = QPushButton("Log Intensity")
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.logIntensityButton.sizePolicy().hasHeightForWidth())
        self.logIntensityButton.setSizePolicy(sizePolicy)
        self.logIntensityButton.setObjectName("logIntensity")
        self.ui.gridLayout.addWidget(self.logIntensityButton, 3, 2, 1, 1)
        self.logIntensityButton.setCheckable(True)
        self.setLogScale(True)
        self.logIntensityButton.clicked.connect(self._setLogScale)

    def _setLogScale(self, value):
        self.imageItem.logScale = value
        self.imageItem.qimage = None
        self.imageItem.update()
        self.getHistogramWidget().region.setBounds([0 if value else None, None])

    def setLogScale(self, value):
        self._setLogScale(value)
        self.logIntensityButton.setChecked(value)


class CatalogView(ImageView):
    def quickMinMax(self, data):
        """
        Estimate the min/max values of *data* by subsampling. MODIFIED TO USE THE 99TH PERCENTILE instead of max.
        """
        if data is None:
            return 0, 0

        sl = slice(None, None, max(1, int(data.size // 1e6)))
        data = np.asarray(data[sl])
        return (np.nanmin(data), np.nanpercentile(np.where(data < np.nanmax(data), data, np.nanmin(data)), 99))
