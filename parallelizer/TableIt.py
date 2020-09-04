import os
import math
import random

def initColors():
    os.system("cls")

def findLargestElement(rows, cols, lengthArray, matrix):
    # Loop through each row
    for i in range(rows):  
        # Loop through each column
        for j in range(cols):
            lengthArray.append(len(str(matrix[i][j])))
    # Sort the length matrix so that we can find the element with the longest length
    lengthArray.sort()
    # Store that length
    largestElementLength = lengthArray[-1]

    return largestElementLength


def createMatrix(rows, cols, matrixToWorkOn, matrix):
    # Loop through each row
    for i in range(rows):    
        # Append a row to matrixToWorkOn for each row in the matrix passed in
        matrixToWorkOn.append([])
        # Loop through each column
        for j in range(cols):
            # Add a each column of the current row (in string form) to matrixToWorkOn
            matrixToWorkOn[i].append(str(matrix[i][j]))

def makeRows(rows, cols, largestElementLength, rowLength, matrixToWorkOn, finalTable, color):

    # Loop through each row
    for i in range(rows):
        # Initialize the row that will we work on currently as a blank string
        currentRow = ""
        # Loop trhough each column
        for j in range(cols):
            # If we are using colors then do the same thing but as without (below)
            if ((color != None) and (j == 0 or i == 0)):
                # Only add color if it is in the first column or first row
                currentEl = " " + "\033[38;2;" + str(color[0]) + ";" + str(color[1]) + ";" + str(color[2]) +"m" + matrixToWorkOn[i][j] + "\033[0m"
            # If we are not using colors (or j != 0 or i != 0) just add a space and the element that should be in that position to a variable which will store the current element to work on
            else:
                currentEl = " " + matrixToWorkOn[i][j]

            # If the raw element is less than the largest length of a raw element (raw element is just the unformatted element passed in)
            if (largestElementLength != len(matrixToWorkOn[i][j])):
                # If we are using colors then add the amount of spaces that is equal to the difference of the largest element length and the current element (minus the length that is added for the color)
                # * The plus two here comes from the one space we would normally need and the fact that we need to account for a space that tbe current element already has
                if (color != None):
                    if (j == 0 or i == 0):
                        currentEl = currentEl + " " * (largestElementLength - (len(currentEl) - len("\033[38;2;" + str(color[0]) + ";" + str(color[1]) + ";" + str(color[2]) + "m" + "\033[0m")) + 2) + "|"
                    # If it is not the first column or first row than it doesn't need to subtract the color length
                    else:
                        currentEl = currentEl + " " * (largestElementLength - len(currentEl) + 2) + "|"
                # If we are not using color just do the same thing as above when we were using colors for when the row or column is not the first each time
                else:
                    currentEl = currentEl + " " * (largestElementLength - len(currentEl) + 2) + "|"
            # If the raw element length us equal to the largest length of a raw element then we don't need to add extra spaces
            else:
                currentEl = currentEl + " " + "|"
            # Now add the current element to the row that we are working on
            currentRow += currentEl
        # When the entire row that we were working on is done add it as a row to the final table that we will print
        finalTable.append("|" + currentRow)
    # If we are using color then the length of each row (each row will end up being the same length) equals to the length of the last row (again each row will end up being the same length) minus the length the color will inevitably add if we are using colors
    if (color != None):
        rowLength = len(currentRow) - len("\033[38;2;" + str(color[0]) + ";" + str(color[1]) + ";" + str(color[2]) + "m" + "\033[0m")
    # Otherwise (we are not using colors) the length of each row will be equal to the length of the last row (each row will end up being the same length)
    else:
        rowLength = len(currentRow)  
    
    return rowLength

def createWrappingRows(rowLength, finalTable):
    # Here we deal with the rows that will go on the top and bottom of the table (look like -> +--------------+), we start by initializing an empty string
    wrappingRows = ""
    # Then for the length of each row minus one (have to account for the plus that comes at the end, not minus two because rowLength doesn't include the | at the beginning) we add a -
    for i in range(rowLength - 1):
        wrappingRows += "-"
    # Add a plus at the beginning
    wrappingRows = "+" + wrappingRows
    # Add a plus at the end
    wrappingRows += "+"

     # Add the two wrapping rows
    finalTable.insert(0, wrappingRows)
    finalTable.append(wrappingRows)

def createRowUnderFields(largestElementLength, cols, finalTable):
    # Initialize the row that will be created 
    rowUnderFields = ""
    # Loop through each column
    for j in range(cols):
        # For each column add a plus
        currentElUnderField = "+" 
        # Then add an amount of -'s equal to the length of largest raw element and add 2 for the 2 spaces that will be either side the element
        currentElUnderField = currentElUnderField + "-" * (largestElementLength + 2)
        # Then add the current element (there will be one for each column) to the final row that will be under the fields
        rowUnderFields += currentElUnderField
    # Add a final plus at the end of the row
    rowUnderFields += "+"
    # Insert this row under the first row
    finalTable.insert(2, rowUnderFields)


def printRowsInTable(finalTable):
    # For each row - print it
    for row in finalTable:
        print(row)

def printTable(matrix, useFieldNames=False, color=None):
    # Rows equal amount of lists inside greater list
    rows = len(matrix)
    # Cols equal amount of elements inside each list
    cols = len(matrix[0])
    # This is the array to sort the length of each element
    lengthArray = []
    # This is the variable to store the vakye of the largest length of any element
    largestElementLength = None
    #This is the variable that will store the length of each row
    rowLength = None
    # This is the matrix that we will work with throughout this program (main difference between matrix passed in and this matrix is that the matrix that is passed in doesn't always have elements which are all strings)
    matrixToWorkOn = []
    #This the list in which each row will be one of the final table to be printed
    finalTable = []

    largestElementLength = findLargestElement(rows, cols, lengthArray, matrix)
    createMatrix(rows, cols, matrixToWorkOn, matrix)
    rowLength = makeRows(rows, cols, largestElementLength, rowLength, matrixToWorkOn, finalTable, color)
    createWrappingRows(rowLength, finalTable)
    if (useFieldNames):
        createRowUnderFields(largestElementLength, cols, finalTable)
    printRowsInTable(finalTable)
