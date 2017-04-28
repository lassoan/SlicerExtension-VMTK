# slicer imports
import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

#from __main__ import vtk, qt, ctk, slicer

# vmtk includes
import SlicerVmtkCommonLib


#
# Vesselness Filtering using VMTK based Tools
#

class VesselnessFiltering(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Vesselness Filtering"
    self.parent.categories = ["Vascular Modeling Toolkit"]
    self.parent.dependencies = []
    self.parent.contributors = ["Daniel Haehn (Boston Children's Hospital)", "Luca Antiga (Orobix)", "Steve Pieper (Isomics)", "Andras Lasso (PerkLab)"]
    self.parent.helpText = """
"""
    self.parent.acknowledgementText = """
""" # replace with organization, grant and thanks.

#
# VesselnessFilteringWidget
#


class VesselnessFilteringWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__( self, parent=None ):
    ScriptedLoadableModuleWidget.__init__(self, parent)
    self.logic = VesselnessFilteringLogic()

    if not parent:
      # after setup, be ready for events
      self.parent.show()
    else:
      # register default slots
      self.parent.connect( 'mrmlSceneChanged(vtkMRMLScene*)', self.onMRMLSceneChanged )

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    try:
      import vtkvmtkSegmentationPython as vtkvmtkSegmentation
    except ImportError:
      self.layout.addWidget(qt.QLabel("Failed to load VMTK libraries"))
      return

    #
    # the I/O panel
    #

    ioCollapsibleButton = ctk.ctkCollapsibleButton()
    ioCollapsibleButton.text = "Input/Output"
    self.layout.addWidget( ioCollapsibleButton )
    ioFormLayout = qt.QFormLayout( ioCollapsibleButton )

    # inputVolume selector
    self.__inputVolumeNodeSelector = slicer.qMRMLNodeComboBox()
    self.__inputVolumeNodeSelector.objectName = 'inputVolumeNodeSelector'
    self.__inputVolumeNodeSelector.toolTip = "Select the input volume."
    self.__inputVolumeNodeSelector.nodeTypes = ['vtkMRMLScalarVolumeNode']
    self.__inputVolumeNodeSelector.noneEnabled = False
    self.__inputVolumeNodeSelector.addEnabled = False
    self.__inputVolumeNodeSelector.removeEnabled = False
    ioFormLayout.addRow( "Input Volume:", self.__inputVolumeNodeSelector )
    self.parent.connect( 'mrmlSceneChanged(vtkMRMLScene*)',
                        self.__inputVolumeNodeSelector, 'setMRMLScene(vtkMRMLScene*)' )

    # seed selector
    self.__seedFiducialsNodeSelector = slicer.qSlicerSimpleMarkupsWidget()
    self.__seedFiducialsNodeSelector.objectName = 'seedFiducialsNodeSelector'
    self.__seedFiducialsNodeSelector = slicer.qSlicerSimpleMarkupsWidget()
    self.__seedFiducialsNodeSelector.objectName = 'seedFiducialsNodeSelector'
    self.__seedFiducialsNodeSelector.toolTip = "Select a point in the largest vessel. Preview will be shown around this point. This is point is also used for determining maximum vessel diameter if automatic filtering parameters computation is enabled."
    self.__seedFiducialsNodeSelector.setNodeBaseName("DiameterSeed")
    self.__seedFiducialsNodeSelector.tableWidget().hide()
    self.__seedFiducialsNodeSelector.defaultNodeColor = qt.QColor(255,0,0) # red
    self.__seedFiducialsNodeSelector.markupsSelectorComboBox().noneEnabled = False
    self.__seedFiducialsNodeSelector.markupsPlaceWidget().placeMultipleMarkups = slicer.qSlicerMarkupsPlaceWidget.ForcePlaceSingleMarkup
    ioFormLayout.addRow( "Seed point:", self.__seedFiducialsNodeSelector )
    self.parent.connect( 'mrmlSceneChanged(vtkMRMLScene*)',
                        self.__seedFiducialsNodeSelector, 'setMRMLScene(vtkMRMLScene*)' )

    # outputVolume selector
    self.__outputVolumeNodeSelector = slicer.qMRMLNodeComboBox()
    self.__outputVolumeNodeSelector.toolTip = "Select the output labelmap."
    self.__outputVolumeNodeSelector.nodeTypes = ['vtkMRMLScalarVolumeNode']
    self.__outputVolumeNodeSelector.baseName = "VesselnessFiltered"
    self.__outputVolumeNodeSelector.noneEnabled = True
    self.__outputVolumeNodeSelector.noneDisplay = "Create new volume"
    self.__outputVolumeNodeSelector.addEnabled = True
    self.__outputVolumeNodeSelector.selectNodeUponCreation = True
    self.__outputVolumeNodeSelector.removeEnabled = True
    ioFormLayout.addRow( "Output Volume:", self.__outputVolumeNodeSelector )
    self.parent.connect( 'mrmlSceneChanged(vtkMRMLScene*)',
                        self.__outputVolumeNodeSelector, 'setMRMLScene(vtkMRMLScene*)' )
                        
    #
    # Advanced area
    #

    self.advancedCollapsibleButton = ctk.ctkCollapsibleButton()
    self.advancedCollapsibleButton.text = "Advanced"
    self.advancedCollapsibleButton.collapsed = True
    self.layout.addWidget(self.advancedCollapsibleButton)
    advancedFormLayout = qt.QFormLayout(self.advancedCollapsibleButton)

    # previewVolume selector
    self.__previewVolumeNodeSelector = slicer.qMRMLNodeComboBox()
    self.__previewVolumeNodeSelector.toolTip = "Select the preview volume."
    self.__previewVolumeNodeSelector.nodeTypes = ['vtkMRMLScalarVolumeNode']
    self.__previewVolumeNodeSelector.baseName = "VesselnessPreview"
    self.__previewVolumeNodeSelector.noneEnabled = False
    self.__previewVolumeNodeSelector.addEnabled = True
    self.__previewVolumeNodeSelector.selectNodeUponCreation = True
    self.__previewVolumeNodeSelector.removeEnabled = True
    advancedFormLayout.addRow( "Preview volume:", self.__previewVolumeNodeSelector )
    self.parent.connect( 'mrmlSceneChanged(vtkMRMLScene*)',
                        self.__previewVolumeNodeSelector, 'setMRMLScene(vtkMRMLScene*)' )

    self.__previewVolumeDiameterVoxelSlider = ctk.ctkSliderWidget()
    self.__previewVolumeDiameterVoxelSlider.decimals = 0
    self.__previewVolumeDiameterVoxelSlider.minimum = 10
    self.__previewVolumeDiameterVoxelSlider.maximum = 200
    self.__previewVolumeDiameterVoxelSlider.singleStep = 5
    self.__previewVolumeDiameterVoxelSlider.suffix = " voxels"
    self.__previewVolumeDiameterVoxelSlider.toolTip = "Diameter of the preview area in voxels."
    advancedFormLayout.addRow( "Preview volume size:", self.__previewVolumeDiameterVoxelSlider )
                        
    # lock button
    self.__detectPushButton = qt.QPushButton()
    self.__detectPushButton.text = "Compute vessel diameters and contrast from seed point"
    self.__detectPushButton.checkable = True
    self.__detectPushButton.checked = True
    #self.__detectPushButton.connect("clicked()", self.calculateParameters())
    advancedFormLayout.addRow( self.__detectPushButton )                        
                        
    self.__minimumDiameterSpinBox = qt.QSpinBox()
    self.__minimumDiameterSpinBox.minimum = 0
    self.__minimumDiameterSpinBox.maximum = 1000
    self.__minimumDiameterSpinBox.singleStep = 1
    self.__minimumDiameterSpinBox.suffix = " voxels"
    self.__minimumDiameterSpinBox.enabled = False
    self.__minimumDiameterSpinBox.toolTip = "Tubular structures that have minimum this diameter will be enhanced."
    advancedFormLayout.addRow( "Minimum vessel diameter:", self.__minimumDiameterSpinBox )
    self.__detectPushButton.connect("toggled(bool)", self.__minimumDiameterSpinBox.setDisabled)

    self.__maximumDiameterSpinBox = qt.QSpinBox()
    self.__maximumDiameterSpinBox.minimum = 0
    self.__maximumDiameterSpinBox.maximum = 1000
    self.__maximumDiameterSpinBox.singleStep = 1
    self.__maximumDiameterSpinBox.suffix = " voxels"
    self.__maximumDiameterSpinBox.enabled = False
    self.__maximumDiameterSpinBox.toolTip = "Tubular structures that have maximum this diameter will be enhanced."
    advancedFormLayout.addRow( "Maximum vessel diameter:", self.__maximumDiameterSpinBox )
    self.__detectPushButton.connect("toggled(bool)", self.__maximumDiameterSpinBox.setDisabled)

    self.__contrastSlider = ctk.ctkSliderWidget()
    self.__contrastSlider.decimals = 0
    self.__contrastSlider.minimum = 0
    self.__contrastSlider.maximum = 500
    self.__contrastSlider.singleStep = 10
    self.__contrastSlider.enabled = False
    self.__contrastSlider.toolTip = "If the intensity contrast in the input image between vessel and background is high, choose a high value else choose a low value."
    advancedFormLayout.addRow( "Vessel contrast:", self.__contrastSlider )
    self.__detectPushButton.connect("toggled(bool)", self.__contrastSlider.setDisabled)

    self.__suppressPlatesSlider = ctk.ctkSliderWidget()
    self.__suppressPlatesSlider.decimals = 0
    self.__suppressPlatesSlider.minimum = 0
    self.__suppressPlatesSlider.maximum = 100
    self.__suppressPlatesSlider.singleStep = 1
    self.__suppressPlatesSlider.suffix = " %"
    self.__suppressPlatesSlider.toolTip = "A higher value filters out more plate-like structures."
    advancedFormLayout.addRow( "Suppress plates:", self.__suppressPlatesSlider )

    self.__suppressBlobsSlider = ctk.ctkSliderWidget()
    self.__suppressBlobsSlider.decimals = 0
    self.__suppressBlobsSlider.minimum = 0
    self.__suppressBlobsSlider.maximum = 100
    self.__suppressBlobsSlider.singleStep = 1
    self.__suppressBlobsSlider.suffix = " %"
    self.__suppressBlobsSlider.toolTip = "A higher value filters out more blob-like structures."
    advancedFormLayout.addRow( "Suppress blobs:", self.__suppressBlobsSlider )

    #
    # Reset, preview and apply buttons
    #

    self.__buttonBox = qt.QDialogButtonBox()
    self.__resetButton = self.__buttonBox.addButton( self.__buttonBox.RestoreDefaults )
    self.__resetButton.toolTip = "Click to reset all input elements to default."
    self.__previewButton = self.__buttonBox.addButton( self.__buttonBox.Discard )
    self.__previewButton.setIcon( qt.QIcon() )
    self.__previewButton.text = "Preview"
    self.__previewButton.toolTip = "Click to refresh the preview."
    self.__startButton = self.__buttonBox.addButton( self.__buttonBox.Apply )
    self.__startButton.setIcon( qt.QIcon() )
    self.__startButton.text = "Start"
    self.__startButton.enabled = False
    self.__startButton.toolTip = "Click to start the filtering."
    self.layout.addWidget( self.__buttonBox )
    self.__resetButton.connect( "clicked()", self.restoreDefaults )
    self.__previewButton.connect( "clicked()", self.onPreviewButtonClicked )
    self.__startButton.connect( "clicked()", self.onStartButtonClicked )

    self.__inputVolumeNodeSelector.setMRMLScene( slicer.mrmlScene )
    self.__seedFiducialsNodeSelector.setMRMLScene( slicer.mrmlScene )
    self.__outputVolumeNodeSelector.setMRMLScene( slicer.mrmlScene )
    self.__previewVolumeNodeSelector.setMRMLScene( slicer.mrmlScene )

    # set default values
    self.restoreDefaults()

    # compress the layout
    self.layout.addStretch( 1 )

  def onMRMLSceneChanged( self ):
    logging.debug( "onMRMLSceneChanged" )
    self.restoreDefaults()

  def onStartButtonClicked( self ):
    if self.__detectPushButton.checked:
      self.calculateParameters()

    # this is no preview
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
    self.start( False )
    qt.QApplication.restoreOverrideCursor()

  def onPreviewButtonClicked( self ):
      '''
      '''
      if self.__detectPushButton.checked:
          #self.restoreDefaults()
          self.calculateParameters()

      # calculate the preview
      self.start( True )

      # activate startButton
      self.__startButton.enabled = True

  def calculateParameters( self ):
    logging.debug( "calculateParameters" )

    currentVolumeNode = self.__inputVolumeNodeSelector.currentNode()
    if not currentVolumeNode:
      raise ValueError("Input volume node is invalid")

    currentSeedsNode = self.__seedFiducialsNodeSelector.currentNode()
    if not currentVolumeNode:
      raise ValueError("Input seed node is invalid")
      
    vesselPositionIJK = self.logic.getIJKFromRAS(currentVolumeNode, self.logic.getSeedPositionRAS(currentSeedsNode))

    # we detect the diameter in IJK space (image has spacing 1,1,1) with IJK coordinates
    detectedDiameter = self.logic.getDiameter( currentVolumeNode.GetImageData(), vesselPositionIJK)
    logging.debug( "Diameter detected: " + str( detectedDiameter ) )

    contrastMeasure = self.logic.calculateContrastMeasure( currentVolumeNode.GetImageData(), vesselPositionIJK, detectedDiameter )
    logging.debug( "Contrast measure: " + str( contrastMeasure ) )

    self.__maximumDiameterSpinBox.value = detectedDiameter
    self.__contrastSlider.value = contrastMeasure

  def restoreDefaults( self ):
    logging.debug("restoreDefaults")

    self.__detectPushButton.checked = True
    self.__previewVolumeDiameterVoxelSlider.value = 20
    self.__minimumDiameterSpinBox.value = 1
    self.__maximumDiameterSpinBox.value = 7
    self.__suppressPlatesSlider.value = 10
    self.__suppressBlobsSlider.value = 10
    self.__contrastSlider.value = 100

    self.__startButton.enabled = False


  def start( self, preview=False ):
    # first we need the nodes
    currentVolumeNode = self.__inputVolumeNodeSelector.currentNode()
    currentSeedsNode = self.__seedFiducialsNodeSelector.currentNode()

    # Determine output volume node
    if preview:
      # if previewMode, get the node selector of the preview volume
      currentOutputVolumeNodeSelector = self.__previewVolumeNodeSelector
      # preview region
      previewRegionSizeVoxel = self.__previewVolumeDiameterVoxelSlider.value
      previewRegionCenterRAS = self.logic.getSeedPositionRAS(currentSeedsNode)
    else:
      currentOutputVolumeNodeSelector = self.__outputVolumeNodeSelector
      # preview region
      previewRegionSizeVoxel = -1
      previewRegionCenterRAS = None
    currentOutputVolumeNode = currentOutputVolumeNodeSelector.currentNode()
   
   # Create output voluem if does not exist yet
    if not currentOutputVolumeNode or currentOutputVolumeNode.GetID() == currentVolumeNode.GetID():
      newVolumeNode = slicer.mrmlScene.CreateNodeByClass( "vtkMRMLScalarVolumeNode" )
      newVolumeNode.UnRegister(None)        
      newVolumeNode.SetName( slicer.mrmlScene.GetUniqueNameByString( currentOutputVolumeNodeSelector.baseName ) )
      currentOutputVolumeNode = slicer.mrmlScene.AddNode( newVolumeNode )
      currentOutputVolumeNode.CreateDefaultDisplayNodes()
      currentOutputVolumeNodeSelector.setCurrentNode( currentOutputVolumeNode )
      fitToAllSliceViews = True
    else:
      fitToAllSliceViews = False
    
    # we need to convert diameter to mm, we use the minimum spacing to multiply the voxel value
    minimumDiameterMm = self.__minimumDiameterSpinBox.value * min( currentVolumeNode.GetSpacing() )
    maximumDiameterMm = self.__maximumDiameterSpinBox.value * min( currentVolumeNode.GetSpacing() )

    alpha = self.logic.alphaFromSuppressPlatesPercentage(self.__suppressPlatesSlider.value)
    beta = self.logic.alphaFromSuppressPlatesPercentage(self.__suppressBlobsSlider.value)
    contrastMeasure = self.__contrastSlider.value
    
    self.logic.computeVesselnessVolume(currentVolumeNode, currentOutputVolumeNode, previewRegionCenterRAS, previewRegionSizeVoxel,
      minimumDiameterMm, maximumDiameterMm, alpha, beta, contrastMeasure)

    # for preview: show the inputVolume as background and the outputVolume as foreground in the slice viewers
    #    note: that's the only way we can have the preview as an overlay of the originalvolume
    # for not preview: show the outputVolume as background and the inputVolume as foreground in the slice viewers
    if preview:
        fgVolumeID = currentOutputVolumeNode.GetID()
        bgVolumeID = currentVolumeNode.GetID()
    else:
        bgVolumeID = currentOutputVolumeNode.GetID()
        fgVolumeID = currentVolumeNode.GetID()

    selectionNode = slicer.app.applicationLogic().GetSelectionNode()
    selectionNode.SetReferenceActiveVolumeID( bgVolumeID )
    selectionNode.SetReferenceSecondaryVolumeID( fgVolumeID )
    slicer.app.applicationLogic().PropagateVolumeSelection(False)

    # renew auto window/level for the output
    currentOutputVolumeNode.GetDisplayNode().AutoWindowLevelOff()
    currentOutputVolumeNode.GetDisplayNode().AutoWindowLevelOn()

    # show foreground volume
    numberOfCompositeNodes = slicer.mrmlScene.GetNumberOfNodesByClass( 'vtkMRMLSliceCompositeNode' )
    for n in xrange( numberOfCompositeNodes ):
      compositeNode = slicer.mrmlScene.GetNthNodeByClass( n, 'vtkMRMLSliceCompositeNode' )
      if compositeNode:
          if preview:
              # the preview is the foreground volume, so we want to show it fully
              compositeNode.SetForegroundOpacity( 1.0 )
          else:
              # now the background volume is the vesselness output, we want to show it fully
              compositeNode.SetForegroundOpacity( 0.0 )

    # fit slice to all sliceviewers
    if fitToAllSliceViews:
      slicer.app.applicationLogic().FitSliceToAll()

    if preview:
      # jump all sliceViewers to the fiducial point, if one was used
      if currentSeedsNode:
          numberOfSliceNodes = slicer.mrmlScene.GetNumberOfNodesByClass( 'vtkMRMLSliceNode' )
          for n in xrange( numberOfSliceNodes ):
              sliceNode = slicer.mrmlScene.GetNthNodeByClass( n, "vtkMRMLSliceNode" )
              if sliceNode:
                  sliceNode.JumpSliceByOffsetting( previewRegionCenterRAS[0], previewRegionCenterRAS[1], previewRegionCenterRAS[2] )
                  
    logging.debug( "End of Vesselness Filtering" )

class VesselnessFilteringLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self):
    ScriptedLoadableModuleLogic.__init__(self)
    # the pointer to the logic

  def getSeedPositionRAS(self, seedNode):
    if not seedNode:
        raise ValueError("Input seed node is invalid")
    n = seedNode.GetNumberOfFiducials()
    seedPositionRAS = [0, 0, 0]
    seedNode.GetNthFiducialPosition(n-1,seedPositionRAS)
    return seedPositionRAS  

  def getIJKFromRAS(self, volumeNode, ras):
    ijk = SlicerVmtkCommonLib.Helper.ConvertRAStoIJK(volumeNode, ras)
    return [int(ijk[0]), int(ijk[1]), int(ijk[2])]
    
  def alphaFromSuppressPlatesPercentage(self, suppressPlatesPercentage):
    return 0.000 + 3.0 * pow(suppressPlatesPercentage/100.0,2)

  def betaFromSuppressBlobsPercentage(self, suppressBlobsPercentage):
    return 0.001 + 1.0 * pow((100.0-self.suppressBlobsPercentage.value)/100.0,2)

  def computeVesselnessVolume(self, currentVolumeNode, currentOutputVolumeNode,
    previewRegionCenterRAS=None, previewRegionSizeVoxel=-1, minimumDiameterMm=0, maximumDiameterMm=25,
    alpha=0.3, beta=0.3, contrastMeasure=150):

    logging.debug("Starting Vesselness Filtering: diameter min={0}, max={1}, alpha={2}, beta={3}, contrastMeasure={4}".format(
      minimumDiameterMm, maximumDiameterMm, alpha, beta, contrastMeasure))

    if not currentVolumeNode:
      raise ValueError("Output volume node is invalid")

    # this image will later hold the inputImage
    inImage = vtk.vtkImageData()

    # if we are in previewMode, we have to cut the ROI first for speed
    if previewRegionSizeVoxel>0:
        # we extract the ROI of currentVolumeNode and save it to currentOutputVolumeNode
        # we work in RAS space
        imageclipper = vtk.vtkImageConstantPad()
        imageclipper.SetInputData(currentVolumeNode.GetImageData())
        previewRegionCenterIJK = self.getIJKFromRAS(currentVolumeNode, previewRegionCenterRAS)
        previewRegionRadiusVoxel = int(round(previewRegionSizeVoxel/2+0.5))
        imageclipper.SetOutputWholeExtent(
          previewRegionCenterIJK[0]-previewRegionRadiusVoxel, previewRegionCenterIJK[0]+previewRegionRadiusVoxel,
          previewRegionCenterIJK[1]-previewRegionRadiusVoxel, previewRegionCenterIJK[1]+previewRegionRadiusVoxel,
          previewRegionCenterIJK[2]-previewRegionRadiusVoxel, previewRegionCenterIJK[2]+previewRegionRadiusVoxel)
        imageclipper.Update()
        currentOutputVolumeNode.SetAndObserveImageData(imageclipper.GetOutput())
        currentOutputVolumeNode.CopyOrientation(currentVolumeNode)
        currentOutputVolumeNode.ShiftImageDataExtentToZeroStart()
        inImage.DeepCopy(currentOutputVolumeNode.GetImageData())
    else:
        # there was no ROI extraction, so just clone the inputImage
        inImage.DeepCopy(currentVolumeNode.GetImageData())
        currentOutputVolumeNode.CopyOrientation( currentVolumeNode )

    # temporarily set spacing to allow vesselness computation performed in physical space
    inImage.SetSpacing( currentVolumeNode.GetSpacing() )

    # we now compute the vesselness in RAS space, inImage has spacing and origin attached, the diameters are converted to mm
    # we use RAS space to support anisotropic datasets
    
    import vtkvmtkSegmentationPython as vtkvmtkSegmentation

    cast = vtk.vtkImageCast()
    cast.SetInputData( inImage )
    cast.SetOutputScalarTypeToFloat()
    cast.Update()
    inImage = cast.GetOutput()

    discretizationSteps = 5
    
    v = vtkvmtkSegmentation.vtkvmtkVesselnessMeasureImageFilter()
    v.SetInputData( inImage )
    v.SetSigmaMin( minimumDiameterMm )
    v.SetSigmaMax( maximumDiameterMm )
    v.SetNumberOfSigmaSteps( discretizationSteps )
    v.SetAlpha( alpha )
    v.SetBeta( beta )
    v.SetGamma( contrastMeasure )
    v.Update()

    outImage = vtk.vtkImageData()
    outImage.DeepCopy( v.GetOutput() )
    outImage.GetPointData().GetScalars().Modified()    

    # restore Slicer-compliant image spacing
    outImage.SetSpacing( 1, 1, 1 )

    # we set the outImage which has spacing 1,1,1. The ijkToRas matrix of the node will take care of that
    currentOutputVolumeNode.SetAndObserveImageData( outImage )

    # save which volume node vesselness filterint result was saved to
    currentVolumeNode.SetAndObserveNodeReferenceID("Vesselness", currentOutputVolumeNode.GetID())
                  
    logging.debug( "End of Vesselness Filtering" )


  def getDiameter( self, image, ijk ):
      edgeImage = self.performLaplaceOfGaussian( image )

      foundDiameter = False

      edgeImageSeedValue = edgeImage.GetScalarComponentAsFloat(ijk[0], ijk[1], ijk[2], 0)
      seedValueSign = cmp( edgeImageSeedValue, 0 )  # returns 1 if >0 or -1 if <0

      # the list of hits
      # [left, right, top, bottom, front, back]
      hits = [False, False, False, False, False, False]

      distanceFromSeed = 1
      while not foundDiameter:

          if ( distanceFromSeed >= edgeImage.GetDimensions()[0]
              or distanceFromSeed >= edgeImage.GetDimensions()[1]
              or distanceFromSeed >= edgeImage.GetDimensions()[2] ):
              # we are out of bounds
              break

          # get the values for the lookahead directions in the edgeImage
          edgeValues = [edgeImage.GetScalarComponentAsFloat( ijk[0] - distanceFromSeed, ijk[1], ijk[2], 0 ),  # left
                        edgeImage.GetScalarComponentAsFloat( ijk[0] + distanceFromSeed, ijk[1], ijk[2], 0 ),  # right
                        edgeImage.GetScalarComponentAsFloat( ijk[0], ijk[1] + distanceFromSeed, ijk[2], 0 ),  # top
                        edgeImage.GetScalarComponentAsFloat( ijk[0], ijk[1] - distanceFromSeed, ijk[2], 0 ),  # bottom
                        edgeImage.GetScalarComponentAsFloat( ijk[0], ijk[1], ijk[2] + distanceFromSeed, 0 ),  # front
                        edgeImage.GetScalarComponentAsFloat( ijk[0], ijk[1], ijk[2] - distanceFromSeed, 0 )]  # back

          # first loop, check if we have hits
          for v in range( len( edgeValues ) ):

              if not hits[v] and cmp( edgeValues[v], 0 ) != seedValueSign:
                  # hit
                  hits[v] = True

          # now check if we have two hits in opposite directions
          if hits[0] and hits[1]:
              # we have the diameter!
              foundDiameter = True
              break

          if hits[2] and hits[3]:
              foundDiameter = True
              break

          if hits[4] and hits[5]:
              foundDiameter = True
              break

          # increase distance from seed for next iteration
          distanceFromSeed += 1

      # we now just return the distanceFromSeed
      # if the diameter was not detected properly, this can equal one of the image dimensions
      return distanceFromSeed


  def performLaplaceOfGaussian( self, image ):
      '''
      '''

      gaussian = vtk.vtkImageGaussianSmooth()
      gaussian.SetInputData( image )
      gaussian.Update()

      laplacian = vtk.vtkImageLaplacian()
      laplacian.SetInputData( gaussian.GetOutput() )
      laplacian.Update()

      outImageData = vtk.vtkImageData()
      outImageData.DeepCopy( laplacian.GetOutput() )

      return outImageData


  def calculateContrastMeasure( self, image, ijk, diameter ):
      '''
      '''
      seedValue = image.GetScalarComponentAsFloat( ijk[0], ijk[1], ijk[2], 0 )

      outsideValues = [seedValue - image.GetScalarComponentAsFloat( ijk[0] + ( 2 * diameter ), ijk[1], ijk[2], 0 ),  # right
                       seedValue - image.GetScalarComponentAsFloat( ijk[0] - ( 2 * diameter ), ijk[1], ijk[2], 0 ),  # left
                       seedValue - image.GetScalarComponentAsFloat( ijk[0], ijk[1] + ( 2 * diameter ), ijk[2], 0 ),  # top
                       seedValue - image.GetScalarComponentAsFloat( ijk[0], ijk[1] - ( 2 * diameter ), ijk[2], 0 ),  # bottom
                       seedValue - image.GetScalarComponentAsFloat( ijk[0], ijk[1], ijk[2] + ( 2 * diameter ), 0 ),  # front
                       seedValue - image.GetScalarComponentAsFloat( ijk[0], ijk[1], ijk[2] - ( 2 * diameter ), 0 )]  # back

      differenceValue = max( outsideValues )

      contrastMeasure = differenceValue / 10  # get 1/10 of it

      return 2 * contrastMeasure

    
class VesselnessFilteringTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)
    import SampleData
    sampleDataLogic = SampleData.SampleDataLogic()
    self.inputAngioVolume = sampleDataLogic.downloadCTACardio()
    
    self.vesselPositionRas = [176.9, -17.4, 52.7]

    # make the output volume appear in all the slice views
    selectionNode = slicer.app.applicationLogic().GetSelectionNode()
    selectionNode.SetReferenceActiveVolumeID(self.inputAngioVolume.GetID())
    slicer.app.applicationLogic().PropagateVolumeSelection(1)
    
  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_BasicVesselSegmentation()

  def test_BasicVesselSegmentation(self):
    self.delayDisplay("Testing BasicVesselSegmentation")
    
    logic = VesselnessFilteringLogic()
      
    vesselPositionIJK = logic.getIJKFromRAS(self.inputAngioVolume, self.vesselPositionRas)
    detectedDiameter = logic.getDiameter( self.inputAngioVolume.GetImageData(), vesselPositionIJK)
    logging.info( "Diameter detected: " + str( detectedDiameter ) )

    contrastMeasure = logic.calculateContrastMeasure( self.inputAngioVolume.GetImageData(), vesselPositionIJK, detectedDiameter )
    logging.info( "Contrast measure: " + str( contrastMeasure ) )

    previewVolumeNode = slicer.mrmlScene.CreateNodeByClass( "vtkMRMLScalarVolumeNode" )
    previewVolumeNode.UnRegister(None)        
    previewVolumeNode.SetName(slicer.mrmlScene.GetUniqueNameByString('VesselnessPreview'))
    previewVolumeNode = slicer.mrmlScene.AddNode(previewVolumeNode)
    previewVolumeNode.CreateDefaultDisplayNodes()
    
    logic.computeVesselnessVolume(self.inputAngioVolume, previewVolumeNode, previewRegionCenterRAS=self.vesselPositionRas, previewRegionSizeVoxel=detectedDiameter, minimumDiameterMm=0.2, maximumDiameterMm=detectedDiameter, alpha=0.03, beta=0.03, contrastMeasure=200)

    #self.assertIsNotNone( markupsShItemID )
    #self.assertEqual( shNode.GetItemOwnerPluginName(markupsShItemID), 'Markups' )
    
    slicer.util.setSliceViewerLayers(background=self.inputAngioVolume, foreground=previewVolumeNode)
    
    self.delayDisplay('Testing BasicVesselSegmentation completed successfully')
    
class Slicelet( object ):
  """A slicer slicelet is a module widget that comes up in stand alone mode
  implemented as a python class.
  This class provides common wrapper functionality used by all slicer modlets.
  """
  # TODO: put this in a SliceletLib
  # TODO: parse command line arge


  def __init__( self, widgetClass=None ):
    self.parent = qt.QFrame()
    self.parent.setLayout( qt.QVBoxLayout() )

    # TODO: should have way to pop up python interactor
    self.buttons = qt.QFrame()
    self.buttons.setLayout( qt.QHBoxLayout() )
    self.parent.layout().addWidget( self.buttons )
    self.addDataButton = qt.QPushButton( "Add Data" )
    self.buttons.layout().addWidget( self.addDataButton )
    self.addDataButton.connect( "clicked()", slicer.app.ioManager().openAddDataDialog )
    self.loadSceneButton = qt.QPushButton( "Load Scene" )
    self.buttons.layout().addWidget( self.loadSceneButton )
    self.loadSceneButton.connect( "clicked()", slicer.app.ioManager().openLoadSceneDialog )

    if widgetClass:
      self.widget = widgetClass( self.parent )
      self.widget.setup()
    self.parent.show()

class VesselnessFilteringSlicelet( Slicelet ):
  """ Creates the interface when module is run as a stand alone gui app.
  """

  def __init__( self ):
    super( VesselnessFilteringSlicelet, self ).__init__( VesselnessFilteringWidget )


if __name__ == "__main__":
 # TODO: need a way to access and parse command line arguments
 # TODO: ideally command line args should handle --xml

 import sys
 print( sys.argv )

 slicelet = VesselnessFilteringSlicelet()
