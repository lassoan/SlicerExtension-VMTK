# slicer imports
from __main__ import vtk, slicer

# python includes
import sys
import time

class Helper(object):

    @staticmethod
    def ConvertRAStoIJK(volumeNode,rasCoordinates):
        '''
        '''
        rasToIjkMatrix = vtk.vtkMatrix4x4()
        volumeNode.GetRASToIJKMatrix(rasToIjkMatrix)

        # the RAS coordinates need to be 4
        if len(rasCoordinates) < 4:
            rasCoordinates.append(1)

        ijkCoordinates = rasToIjkMatrix.MultiplyPoint(rasCoordinates)

        return ijkCoordinates
